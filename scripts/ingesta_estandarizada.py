# -*- coding: utf-8 -*-
"""
Standardized ingestion: receives a minimal payload (tipo_ingesta, fecha, plus
only what the template marks as variable) via repository_dispatch, resolves
everything else against config/plantillas_estandarizadas.json + Supabase, and
inserts into seguimiento_efectivo. Reports the result through Telegram.

Nothing that can be resolved elsewhere is assumed: id_categoria is always
resolved by codigo_categoria + validity date in Supabase (SCD2), medio_pago is
set by the database trigger from the account, and tipo is always the one of
the resolved category.

Template shapes (see config/README.md):
  - simple:  one row, optional fixed amount (importe_fijo) or variable (monto).
  - filas:   several linked rows (savings deposit/withdrawal, card payment).
             A row with id_cuenta=null uses the payload account ("cuenta");
             "cuenta_payload": "cuenta_destino" takes the payload's
             "cuenta_destino" instead (e.g. which credit card is being paid).

The real work lives in procesar_ingesta_estandarizada() - it never calls
Telegram or sys.exit, it only raises. main() decides what to do with errors.
"""
import json
import os
import sys

from motor_supabase import (
    CURRENCY_SYMBOL,
    notificar_telegram,
    resolver_categoria,
    resolver_id_cuenta_por_nombre,
    resolver_nombre_etiqueta_por_id,
    insertar_filas,
    guardar_registro_pendiente,
    NOTA_PENDIENTE,
)

TIPO_INGESTA = os.environ.get("TIPO_INGESTA") or None
FECHA = os.environ.get("FECHA") or None
MONTO = os.environ.get("MONTO") or None
CUENTA_SHORTCUT = os.environ.get("CUENTA") or None
CUENTA_DESTINO = os.environ.get("CUENTA_DESTINO") or None
COMENTARIO_SHORTCUT = os.environ.get("COMENTARIO") or None


def importe_a_float(valor):
    """The Shortcut may send the decimal with comma or dot depending on the
    iPhone regional format ("3,3" or "3.3") - normalized here."""
    return float(str(valor).replace(",", "."))


PLANTILLAS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "plantillas_estandarizadas.json"
)


def cargar_version_vigente(tipo_ingesta, fecha):
    with open(PLANTILLAS_PATH, encoding="utf-8") as f:
        plantillas = json.load(f)

    versiones = plantillas.get(tipo_ingesta)
    if not versiones:
        raise ValueError(f"tipo_ingesta '{tipo_ingesta}' does not exist in plantillas_estandarizadas.json")

    for version in versiones:
        inicio = version["fecha_inicio"]
        fin = version.get("fecha_fin")
        if inicio <= fecha and (fin is None or fecha <= fin):
            return version

    raise ValueError(f"No valid version of template '{tipo_ingesta}' for date {fecha}")


def resolver_categoria_o_falla(codigo_categoria, fecha):
    categoria = resolver_categoria(codigo_categoria, fecha)
    if categoria is None:
        raise ValueError(f"No valid version of category '{codigo_categoria}' for date {fecha}")
    return categoria


def calcular_comentario(version, categoria, comentario_shortcut):
    if "comentario_fijo" in version:
        return version["comentario_fijo"]

    if "comentario_fuente" in version:
        fuente = version["comentario_fuente"]
        if fuente == "categorias.glosa":
            return categoria.get("glosa")
        raise ValueError(f"Unknown comment source: {fuente}")

    if version.get("comentario_desde_shortcut"):
        if not comentario_shortcut:
            raise ValueError("This ingestion type requires 'comentario' from the Shortcut and it did not arrive")
        return comentario_shortcut

    return None


def resolver_monto(version, monto):
    if version.get("importe_fijo") is not None:
        return version["importe_fijo"]
    if monto is None:
        raise ValueError("This ingestion type requires 'monto' from the Shortcut and it did not arrive")
    return abs(importe_a_float(monto)) * version["signo"]


def resolver_cuenta(id_cuenta_plantilla, cuenta_shortcut):
    if id_cuenta_plantilla is not None:
        return id_cuenta_plantilla
    if not cuenta_shortcut:
        raise ValueError("This ingestion type requires an account name ('cuenta') from the Shortcut and it did not arrive")
    id_cuenta = resolver_id_cuenta_por_nombre(cuenta_shortcut)
    if id_cuenta is None:
        raise ValueError(f"No account named '{cuenta_shortcut}'")
    return id_cuenta


def construir_fila_simple(version, fecha, monto, cuenta_shortcut, comentario_shortcut):
    categoria = resolver_categoria_o_falla(version["codigo_categoria"], fecha)
    return {
        "nombre_operacion": version["nombre_operacion"],
        "importe": resolver_monto(version, monto),
        "fecha_operacion": fecha,
        "id_cuenta": resolver_cuenta(version["id_cuenta"], cuenta_shortcut),
        "id_categoria": categoria["id_categoria"],
        "id_etiqueta": version["id_etiqueta"],
        "comentario": calcular_comentario(version, categoria, comentario_shortcut),
        "tipo": categoria["tipo"],
    }


def construir_filas_multiples(version, fecha, monto, cuenta_shortcut, cuenta_destino, comentario_shortcut):
    """Linked rows (savings, card payment). The amount is always positive in
    the payload; each row applies its own sign."""
    if monto is None:
        raise ValueError("This ingestion type requires 'monto' from the Shortcut and it did not arrive")
    monto_abs = abs(importe_a_float(monto))

    categoria = resolver_categoria_o_falla(version["codigo_categoria"], fecha)
    comentario = calcular_comentario(version, categoria, comentario_shortcut)

    payload_cuentas = {"cuenta": cuenta_shortcut, "cuenta_destino": cuenta_destino}
    filas = []
    for fila_def in version["filas"]:
        nombre_cuenta = payload_cuentas[fila_def.get("cuenta_payload", "cuenta")]
        filas.append({
            "nombre_operacion": fila_def["nombre_operacion"],
            "importe": monto_abs * fila_def["signo"],
            "fecha_operacion": fecha,
            "id_cuenta": resolver_cuenta(fila_def["id_cuenta"], nombre_cuenta),
            "id_categoria": categoria["id_categoria"],
            "id_etiqueta": version["id_etiqueta"],
            "comentario": comentario,
            "tipo": categoria["tipo"],
        })
    return filas


def procesar_ingesta_estandarizada(tipo_ingesta, fecha, monto, cuenta_shortcut, comentario_shortcut,
                                   cuenta_destino=None):
    """Does the real work from the Shortcut's raw payload. Raises
    ValueError/RuntimeError on any failure - it never calls Telegram or
    sys.exit, the caller decides."""
    if not tipo_ingesta:
        raise ValueError("Missing 'tipo_ingesta' in payload")
    if not fecha:
        raise ValueError("Missing 'fecha' in payload (there is never a default date)")

    version = cargar_version_vigente(tipo_ingesta, fecha)

    if "filas" in version:
        filas = construir_filas_multiples(
            version, fecha, monto, cuenta_shortcut, cuenta_destino, comentario_shortcut
        )
    else:
        filas = [construir_fila_simple(version, fecha, monto, cuenta_shortcut, comentario_shortcut)]

    resultado = insertar_filas(filas)
    if not resultado.ok:
        raise RuntimeError(f"Supabase rejected the insert ({resultado.status_code}): {resultado.text}")

    return resultado.json(), filas[0]["id_etiqueta"]


def notificar_exito(tipo_ingesta, filas_insertadas, id_etiqueta):
    etiqueta = resolver_nombre_etiqueta_por_id(id_etiqueta) or id_etiqueta
    resumen = "\n".join(
        "  - {tipo}: {nombre} — {importe}{simbolo} — label: {etiqueta}".format(
            tipo="Income" if float(fila["importe"]) > 0 else "Expense",
            nombre=fila["nombre_operacion"],
            importe=fila["importe"],
            simbolo=CURRENCY_SYMBOL,
            etiqueta=etiqueta,
        )
        for fila in filas_insertadas
    )
    ids = ", ".join(fila["id_operacion"] for fila in filas_insertadas)
    notificar_telegram(f"✅ Ingestion '{tipo_ingesta}' recorded:\n{resumen}\nIDs: {ids}")
    print(f"OK: {ids}")


def main():
    payload = {
        "tipo_ingesta": TIPO_INGESTA,
        "fecha": FECHA,
        "monto": MONTO,
        "cuenta": CUENTA_SHORTCUT,
        "cuenta_destino": CUENTA_DESTINO,
        "comentario": COMENTARIO_SHORTCUT,
    }

    try:
        filas_insertadas, id_etiqueta = procesar_ingesta_estandarizada(
            TIPO_INGESTA, FECHA, MONTO, CUENTA_SHORTCUT, COMENTARIO_SHORTCUT, CUENTA_DESTINO
        )
    except Exception as e:
        id_pendiente = guardar_registro_pendiente("ingesta_estandarizada", payload, error_detalle=str(e))
        notificar_telegram(f"❌ Ingestion '{TIPO_INGESTA}' failed ({id_pendiente}): {e}\n{NOTA_PENDIENTE}")
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    notificar_exito(TIPO_INGESTA, filas_insertadas, id_etiqueta)


if __name__ == "__main__":
    main()
