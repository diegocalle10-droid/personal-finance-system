# -*- coding: utf-8 -*-
"""
Dynamic expense (NFC / manual hub): one account, optionally a date, and 1-3
expense lines (amount + category + a short text describing the purchase). The
user picks the category in the Shortcut (it drives the budget).

The LABEL is NOT decided by an AI. It is resolved by deterministic KEYWORD
MATCHING against the current vocabulary of `etiquetas` (read live from
Supabase, no cache), bounded by the chosen category (posibles_categorias). If
no keyword matches, the operation becomes a registros_pendientes record for
the nightly routine (Claude) to classify. Instant, free and no network call
for the label.

When no 'fecha' arrives, the workflow run date is used (time zone TZ_SISTEMA)
- meant for NFC, which fires at the exact moment of payment.

The real work lives in procesar_gasto_dinamico() - it never calls Telegram or
sys.exit, it only raises. main() decides what to do; on failure the pending
record is handled by the nightly Claude routine.
"""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from motor_supabase import (
    SUPABASE_URL,
    REST_HEADERS,
    TZ_SISTEMA,
    CURRENCY_SYMBOL,
    notificar_telegram,
    normalizar,
    resolver_categoria,
    resolver_id_cuenta_por_nombre,
    resolver_signo,
    insertar_filas,
    guardar_registro_pendiente,
    NOTA_PENDIENTE,
)

CUENTA_SHORTCUT = os.environ.get("CUENTA") or None
FECHA_SHORTCUT = os.environ.get("FECHA") or None
LINEAS_RAW = os.environ.get("LINEAS") or None

ZONA = ZoneInfo(TZ_SISTEMA)


def normalizar_importe(importe):
    """The Shortcut may send the decimal with comma or dot depending on the
    iPhone regional format - normalized here."""
    return float(str(importe).replace(",", "."))


def resolver_fecha(fecha_shortcut):
    if fecha_shortcut:
        return fecha_shortcut
    return datetime.now(ZONA).date().isoformat()


def listar_etiquetas_para_matcher():
    """Current vocabulary read live from Supabase: id, name, keyword[],
    posibles_categorias[]. No cache (one datum, one place)."""
    url = f"{SUPABASE_URL}/rest/v1/etiquetas"
    params = {
        "estado": "eq.activa",
        "select": "id_etiqueta,nombre_etiqueta,keyword,posibles_categorias",
    }
    r = requests.get(url, headers=REST_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def resolver_etiqueta_por_keyword(texto, codigo_categoria, etiquetas):
    """Returns (nombre_etiqueta, id_etiqueta) of the label whose keywords have
    the most matches inside the text, bounded to labels whose
    posibles_categorias includes the chosen category. (None, None) when
    nothing matches. The score weighs keyword length so a specific match
    ("pechuga de pollo") beats a generic one ("pollo")."""
    texto_norm = normalizar(texto)
    if not texto_norm:
        return None, None

    mejor = None
    mejor_score = 0
    for e in etiquetas:
        if codigo_categoria not in (e.get("posibles_categorias") or []):
            continue
        score = 0
        for kw in (e.get("keyword") or []):
            kw_norm = normalizar(kw)
            if kw_norm and kw_norm in texto_norm:
                score += len(kw_norm)
        if score > mejor_score:
            mejor_score = score
            mejor = e

    if mejor is None:
        return None, None
    return mejor["nombre_etiqueta"], mejor["id_etiqueta"]


def construir_fila(linea, id_cuenta, fecha, etiquetas):
    codigo_categoria = linea.get("categoria")
    importe = linea.get("importe")

    if not codigo_categoria or importe is None:
        raise ValueError(f"Incomplete line, missing categoria/importe: {linea}")

    categoria = resolver_categoria(codigo_categoria, fecha)
    if categoria is None:
        raise ValueError(f"No valid version of category '{codigo_categoria}' for date {fecha}")

    signo = resolver_signo(categoria["tipo"])
    if signo is None:
        raise ValueError(
            f"Category '{codigo_categoria}' has type '{categoria['tipo']}', "
            "which cannot be recorded as a single row (e.g. a transfer needs 2 linked rows)"
        )

    texto = linea.get("nombre_operacion") or ""
    nombre_etiqueta, id_etiqueta = resolver_etiqueta_por_keyword(texto, codigo_categoria, etiquetas)
    if id_etiqueta is None:
        raise RuntimeError(
            f"No keyword match for '{texto}' in category '{codigo_categoria}' "
            "- moved to pendings for nightly classification"
        )

    return {
        "nombre_operacion": texto or nombre_etiqueta.capitalize(),
        "importe": abs(normalizar_importe(importe)) * signo,
        "fecha_operacion": fecha,
        "id_cuenta": id_cuenta,
        "id_categoria": categoria["id_categoria"],
        "id_etiqueta": id_etiqueta,
        "comentario": linea.get("comentario"),
        "tipo": categoria["tipo"],
    }, nombre_etiqueta


def procesar_gasto_dinamico(cuenta_nombre, lineas_raw, fecha_shortcut):
    """Does the real work from the Shortcut's raw payload. Raises on any
    failure (ValueError invalid data, RuntimeError no-match/Supabase) - never
    Telegram or sys.exit."""
    if not cuenta_nombre:
        raise ValueError("Missing 'cuenta' in payload")
    if not lineas_raw:
        raise ValueError("Missing 'lineas' in payload")

    try:
        lineas = json.loads(lineas_raw) if isinstance(lineas_raw, str) else lineas_raw
    except json.JSONDecodeError:
        raise ValueError(f"'lineas' is not valid JSON: {lineas_raw}")

    if not isinstance(lineas, list) or not (1 <= len(lineas) <= 3):
        cantidad = len(lineas) if isinstance(lineas, list) else "invalid data"
        raise ValueError(f"'lineas' must be a list of 1 to 3 expenses, got: {cantidad}")

    id_cuenta = resolver_id_cuenta_por_nombre(cuenta_nombre)
    if id_cuenta is None:
        raise ValueError(f"No account named '{cuenta_nombre}'")

    # Older Shortcuts put "fecha" inside each line; use it when the top-level date is missing.
    if not fecha_shortcut:
        fecha_shortcut = next((l.get("fecha") for l in lineas if isinstance(l, dict) and l.get("fecha")), None)
    fecha = resolver_fecha(fecha_shortcut)
    etiquetas = listar_etiquetas_para_matcher()

    filas = []
    etiquetas_asignadas = []
    for linea in lineas:
        fila, nombre_etiqueta = construir_fila(linea, id_cuenta, fecha, etiquetas)
        filas.append(fila)
        etiquetas_asignadas.append(nombre_etiqueta)

    resultado = insertar_filas(filas)
    if not resultado.ok:
        raise RuntimeError(f"Supabase rejected the insert ({resultado.status_code}): {resultado.text}")

    return resultado.json(), etiquetas_asignadas, fecha


def notificar_exito(filas_insertadas, etiquetas_asignadas, fecha):
    resumen = "\n".join(
        "  - {tipo}: {nombre} — {importe}{simbolo} — label: {etiqueta}".format(
            tipo="Income" if float(fila["importe"]) > 0 else "Expense",
            nombre=fila["nombre_operacion"],
            importe=fila["importe"],
            simbolo=CURRENCY_SYMBOL,
            etiqueta=etiqueta,
        )
        for fila, etiqueta in zip(filas_insertadas, etiquetas_asignadas)
    )
    ids = ", ".join(fila["id_operacion"] for fila in filas_insertadas)
    notificar_telegram(f"✅ Recorded ({fecha}):\n{resumen}\nIDs: {ids}")
    print(f"OK: {ids}")


def main():
    payload = {"cuenta": CUENTA_SHORTCUT, "fecha": FECHA_SHORTCUT, "lineas": LINEAS_RAW}

    try:
        filas_insertadas, etiquetas_asignadas, fecha = procesar_gasto_dinamico(
            CUENTA_SHORTCUT, LINEAS_RAW, FECHA_SHORTCUT
        )
    except Exception as e:
        id_pendiente = guardar_registro_pendiente("gasto_dinamico", payload, error_detalle=str(e))
        notificar_telegram(f"❌ Dynamic expense failed ({id_pendiente}): {e}\n{NOTA_PENDIENTE}")
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    notificar_exito(filas_insertadas, etiquetas_asignadas, fecha)


if __name__ == "__main__":
    main()
