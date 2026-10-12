# -*- coding: utf-8 -*-
"""
Photo expense (NFC / manual, "with receipt" branch): the Shortcut uploads the
receipt image to Supabase Storage (bucket 'recibos') and sends the account +
the object path that the Shortcut itself generated.

Division of responsibilities (so the AI can never break the budget):
- CATEGORIES are preselected by the user in the Shortcut. The prompt is built
  LIVE with only those categories: a numbered MENU of category/label pairs
  (with examples taken from etiquetas.keyword). The AI only picks a number from
  the menu per product - it never writes category/label names by hand.
- The GLOSSARY overrides the AI: if the keywords of a label recognize the
  product, that option wins over the one the model chose (deterministic).
- AMOUNTS are verified against the TOTAL printed on the receipt. If they do not
  add up one re-read is requested; if they still do not, it becomes a pending.
- DATE is always the workflow run date (time zone TZ_SISTEMA).

The vision AI is Qwen through DashScope (OpenAI-compatible endpoint).
The real work lives in procesar_foto() - it never calls Telegram or sys.exit,
it only raises; main() decides about Telegram and the pending record.

No buttons, no webhook: the rows are inserted directly and Telegram notifies.
If something goes wrong it is corrected by hand afterwards.
"""
import json
import os
import re
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
    resolver_categoria,
    resolver_id_cuenta_por_nombre,
    resolver_signo,
    insertar_filas,
    llamar_qwen_json,
    normalizar,
    guardar_registro_pendiente,
    borrar_registros_pendientes_de_foto,
    NOTA_PENDIENTE,
)

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY")
CUENTA_SHORTCUT = os.environ.get("CUENTA") or None
FOTO_PATH = os.environ.get("FOTO_PATH") or None
CATEGORIAS_RAW = os.environ.get("CATEGORIAS_PERMITIDAS") or None

ZONA = ZoneInfo(TZ_SISTEMA)
MAX_LINEAS = 60  # a real receipt never exceeds this; it is only a sanity limit
MAX_KW_POR_OPCION = 15  # examples per menu option: they guide without bloating the prompt
TOLERANCIA_TOTAL = 0.05  # margin between the sum of lines and the receipt TOTAL
IMPORTES_EJEMPLO = (1.25, 2.40, 3.10, 0.95, 4.60)

INSTRUCCION_USUARIO = "Read this receipt and return the JSON."


class FotoNoEncontrada(Exception):
    """The photo no longer exists in Storage (cleanup already removed it)."""


def parsear_categorias(raw):
    """Normalizes 'categorias' however it arrives from the Shortcut into a clean
    list of codes, without touching the Shortcut (they are fragile to maintain).

    Real cases observed:
    - a correct JSON array: ["groceries", "home"]
    - an array of ONE element with codes glued by quote-comma:
      ["groceries','health_beauty"]  (what the Shortcut sends today)
    - a plain string with separators (comma, newline, ; | etc.)

    Strategy: parse JSON if possible, flatten to pieces, and split each piece by
    quotes / commas / brackets / ; / | / whitespace.
    """
    if raw is None:
        return []

    valor = raw
    try:
        valor = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    piezas = [str(x) for x in valor] if isinstance(valor, list) else [str(valor)]

    codigos = []
    for pieza in piezas:
        for parte in re.split(r"[\s,;|'\"\[\]]+", pieza):
            limpio = parte.strip()
            if limpio:
                codigos.append(limpio)
    return codigos


def listar_etiquetas_completo():
    """Active labels with id, name, posibles_categorias, criterio and keywords.
    It builds the prompt menu and resolves the id without more queries. Live,
    no cache."""
    url = f"{SUPABASE_URL}/rest/v1/etiquetas"
    params = {"estado": "eq.activa", "select": "id_etiqueta,nombre_etiqueta,posibles_categorias,criterio,keyword"}
    r = requests.get(url, headers=REST_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def descargar_foto(path):
    url = f"{SUPABASE_URL}/storage/v1/object/{path}"
    r = requests.get(url, headers=REST_HEADERS, timeout=30)
    if r.status_code == 404:
        raise FotoNoEncontrada(f"Photo '{path}' no longer exists in Supabase Storage")
    if not r.ok:
        raise RuntimeError(f"Could not download photo '{path}' from Supabase Storage ({r.status_code}): {r.text}")
    return r.content


def resolver_categorias_permitidas(codigos, fecha):
    """Validates live against Supabase every codigo_categoria the user
    preselected in the Shortcut. Returns {code: category_info}."""
    resueltas = {}
    for codigo in codigos:
        categoria = resolver_categoria(codigo, fecha)
        if categoria is None:
            raise RuntimeError(f"Preselected category '{codigo}' has no valid version for date {fecha}")
        resueltas[codigo] = categoria
    return resueltas


# --- Dynamic menu: ONLY the categories that arrived from the Shortcut ---

def construir_menu(categorias_permitidas, etiquetas_full):
    """Numbered (category, label) options of the preselected categories, by
    etiquetas.posibles_categorias. A label that lives in two allowed categories
    appears as two options (one per category)."""
    menu = []
    for codigo in categorias_permitidas:
        propias = sorted(
            (e for e in etiquetas_full if codigo in (e.get("posibles_categorias") or [])),
            key=lambda e: e["nombre_etiqueta"],
        )
        if not propias:
            raise RuntimeError(f"Category '{codigo}' has no associated labels (posibles_categorias)")
        for e in propias:
            menu.append({
                "opcion": len(menu) + 1,
                "categoria": codigo,
                "etiqueta": e["nombre_etiqueta"],
                "id_etiqueta": e["id_etiqueta"],
                "criterio": e.get("criterio") or "",
                "keywords": e.get("keyword") or [],
            })
    return menu


def texto_menu(menu):
    """Each option: category / label, its criterion (what tells it apart from
    its siblings) and product examples."""
    return "\n".join(
        f"{o['opcion']} = {o['categoria']} / {o['etiqueta']}"
        + (f" | {o['criterio']}" if o["criterio"] else "")
        + f" | e.g.: {', '.join(o['keywords'][:MAX_KW_POR_OPCION]) or '-'}"
        for o in menu
    )


def construir_ejemplo(menu, categorias_permitidas):
    """Output example generated from the menu itself: one product per received
    category, taken from the examples of its first label. So the example always
    shows the split using THIS receipt's categories."""
    elegidas = []
    for codigo in categorias_permitidas:
        opciones = [o for o in menu if o["categoria"] == codigo and o["keywords"]]
        if opciones:
            elegidas.append(opciones[0])
    if len(elegidas) == 1:  # a single category: two products of different labels
        elegidas += [o for o in menu if o["keywords"] and o["etiqueta"] != elegidas[0]["etiqueta"]][:1]

    lineas = []
    for i, o in enumerate(elegidas):
        kw = o["keywords"][0]
        lineas.append({
            "receipt_text": kw.upper(),
            "amount": IMPORTES_EJEMPLO[i % len(IMPORTES_EJEMPLO)],
            "product": kw.capitalize(),
            "option": o["opcion"],
        })
    total = round(sum(linea["amount"] for linea in lineas), 2)
    return json.dumps({"merchant": "Store name", "total": total, "lines": lineas}, ensure_ascii=False)


def construir_prompt_sistema(menu, categorias_permitidas):
    return f"""You are the purchase-receipt reader of a personal finance system. Your job has two steps: transcribe every product of the receipt with its amount, and assign to every product the menu option that describes what that product IS.

STEP 1 - TRANSCRIBE
- Go through the receipt from top to bottom. Every product of the receipt is its own object in "lines", in the same order as the receipt.
- "receipt_text": the product text copied exactly as it appears.
- "amount": the price printed on THAT SAME row, to the right of the product. Positive number with a decimal point.
- Products sold by weight or in several units: the detail row ("1,268 kg x 1,49 EUR/kg", "2 x 0,85") is part of the product above; its amount is the total of that product.
- Discounts, promotions and coupons: subtract them from the amount of the product they apply to.
- "total": the TOTAL to pay printed on the receipt.
- Final check: the sum of the amounts in "lines" equals "total".

STEP 2 - CLASSIFY
- Every product receives the number of the menu option whose definition describes what the product is. Judge the product, not the store.
- Every product is classified on its own: one receipt splits its products among the menu categories that fit them.
- Among similar options the definition decides; the examples only guide. A product that is not in the examples goes to the option whose definition fits it best.
- "product": a short, readable product name in the language of the receipt.

MENU (number = category / label | definition | product examples)
{texto_menu(menu)}

OUTPUT FORMAT: only this JSON.
Example of the shape (illustrative products, each one in the option matching its nature):
{construir_ejemplo(menu, categorias_permitidas)}
"""


# --- Reading with verification against the receipt TOTAL ---

def _numero(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None


def verificar_total(resultado_ia):
    """(adds_up, sum, total). If the receipt has no readable total, it never blocks."""
    lineas = resultado_ia.get("lines") or []
    suma = round(sum(_numero(linea.get("amount")) or 0 for linea in lineas), 2)
    total = _numero(resultado_ia.get("total"))
    if total is None:
        return True, suma, None
    return abs(suma - total) <= TOLERANCIA_TOTAL, suma, total


def llamar_qwen(imagen_bytes, sistema, instruccion):
    return llamar_qwen_json(instruccion, imagen_bytes, DASHSCOPE_API_KEY, sistema=sistema)  # lets RuntimeError propagate


def leer_ticket(imagen_bytes, sistema):
    """First read; if the sum does not match the TOTAL, ONE re-read with the
    mismatch as a hint. If it still does not match, error -> pending (better to
    review by hand than to put wrong amounts into the budget)."""
    resultado = llamar_qwen(imagen_bytes, sistema, INSTRUCCION_USUARIO)
    cuadra, suma, total = verificar_total(resultado)
    if cuadra:
        return resultado

    relectura = (
        f"{INSTRUCCION_USUARIO}\n\nREVIEW: in a previous read the sum of amounts was {suma:.2f} "
        f"and the printed TOTAL is {total:.2f}. Read the receipt row by row and take, for each "
        "product, the amount on its own row."
    )
    resultado = llamar_qwen(imagen_bytes, sistema, relectura)
    cuadra, suma, total = verificar_total(resultado)
    if not cuadra:
        raise RuntimeError(
            f"The amounts read do not match the receipt total (sum {suma:.2f} vs total {total:.2f}) "
            "- review by hand"
        )
    return resultado


# --- Classification: the glossary rules, the AI covers what the glossary does not know ---

def opciones_por_keyword(texto, menu):
    """Menu options with the best keyword score over the text (whole word,
    accent-free). Score = length of the matching keywords, so specific beats
    generic. [] when nothing matches."""
    texto_norm = normalizar(texto)
    if not texto_norm:
        return []
    puntajes = []
    for o in menu:
        score = 0
        for kw in o["keywords"]:
            kw_norm = normalizar(kw)
            if kw_norm and re.search(rf"\b{re.escape(kw_norm)}\b", texto_norm):
                score += len(kw_norm)
        if score:
            puntajes.append((score, o))
    if not puntajes:
        return []
    mejor = max(score for score, _ in puntajes)
    return [o for score, o in puntajes if score == mejor]


def resolver_opcion(linea, menu, menu_por_id):
    """Returns (option, by_glossary). The glossary overrides the AI when it
    recognizes the product unambiguously; otherwise the AI's option stands."""
    numero = _numero(linea.get("option"))
    opcion_ia = menu_por_id.get(int(numero)) if numero is not None else None

    # The literal receipt text rules; the name the AI writes only counts when the
    # receipt matches nothing (e.g. abbreviations: "YOG GRIEGO" -> "Yogur").
    candidatas = (opciones_por_keyword(linea.get("receipt_text"), menu)
                  or opciones_por_keyword(linea.get("product"), menu))
    if candidatas and opcion_ia not in candidatas:
        if len(candidatas) == 1:
            return candidatas[0], True
        misma_categoria = [o for o in candidatas if opcion_ia and o["categoria"] == opcion_ia["categoria"]]
        if len(misma_categoria) == 1:
            return misma_categoria[0], True

    if opcion_ia is None:
        if candidatas:
            return candidatas[0], True
        raise RuntimeError(f"Incomplete line returned by the AI (option outside the menu): {linea}")
    return opcion_ia, False


def construir_fila(linea, opcion, id_cuenta, fecha, categorias_dict):
    importe = _numero(linea.get("amount"))
    if importe is None:
        raise RuntimeError(f"Incomplete line returned by the AI (no amount): {linea}")

    categoria = categorias_dict[opcion["categoria"]]
    signo = resolver_signo(categoria["tipo"])
    if signo is None:
        raise RuntimeError(
            f"Category '{opcion['categoria']}' has type '{categoria['tipo']}', "
            "which cannot be recorded as a single row (e.g. a transfer needs 2 linked rows)"
        )

    return {
        "nombre_operacion": linea.get("product") or opcion["etiqueta"].capitalize(),
        "importe": abs(importe) * signo,
        "fecha_operacion": fecha,
        "id_cuenta": id_cuenta,
        "id_categoria": categoria["id_categoria"],
        "id_etiqueta": opcion["id_etiqueta"],
        "comentario": linea.get("receipt_text"),
        "tipo": categoria["tipo"],
    }


def procesar_foto(cuenta_nombre, codigos_categoria, foto_path):
    """Does the real work. Returns (inserted_rows, labels, merchant, date) on
    success. Raises FotoNoEncontrada or RuntimeError on failure - never
    Telegram or sys.exit, the caller decides."""
    id_cuenta = resolver_id_cuenta_por_nombre(cuenta_nombre)
    if id_cuenta is None:
        raise RuntimeError(f"No account named '{cuenta_nombre}'")

    hoy = datetime.now(ZONA).date().isoformat()

    categorias_dict = resolver_categorias_permitidas(codigos_categoria, hoy)
    menu = construir_menu(list(categorias_dict), listar_etiquetas_completo())
    menu_por_id = {o["opcion"]: o for o in menu}
    sistema = construir_prompt_sistema(menu, list(categorias_dict))

    imagen_bytes = descargar_foto(foto_path)
    resultado_ia = leer_ticket(imagen_bytes, sistema)

    lineas_ia = resultado_ia.get("lines") or []
    if not (1 <= len(lineas_ia) <= MAX_LINEAS):
        raise RuntimeError(f"The AI returned {len(lineas_ia)} lines, outside the valid range 1-{MAX_LINEAS}")

    filas, etiquetas = [], []
    for linea in lineas_ia:
        opcion, por_glosario = resolver_opcion(linea, menu, menu_por_id)
        filas.append(construir_fila(linea, opcion, id_cuenta, hoy, categorias_dict))
        etiquetas.append(f"{opcion['categoria']} / {opcion['etiqueta']}" + (" (glossary)" if por_glosario else ""))

    resultado = insertar_filas(filas)
    if not resultado.ok:
        raise RuntimeError(f"Supabase rejected the insert ({resultado.status_code}): {resultado.text}")

    comercio = resultado_ia.get("merchant") or "unidentified merchant"
    return resultado.json(), etiquetas, comercio, hoy


def notificar_exito(filas_insertadas, etiquetas, comercio, fecha):
    ids = ", ".join(fila["id_operacion"] for fila in filas_insertadas)
    total = sum(abs(float(fila["importe"])) for fila in filas_insertadas)
    resumen = "\n".join(
        "  - {tipo}: {nombre} — {importe}{simbolo} — {etiqueta}".format(
            tipo="Income" if float(fila["importe"]) > 0 else "Expense",
            nombre=fila["nombre_operacion"],
            importe=fila["importe"],
            simbolo=CURRENCY_SYMBOL,
            etiqueta=etiqueta,
        )
        for fila, etiqueta in zip(filas_insertadas, etiquetas)
    )
    notificar_telegram(
        f"✅ Receipt from {comercio} ({fecha}) — {len(filas_insertadas)} line(s), {total:.2f}{CURRENCY_SYMBOL} total:\n"
        f"{resumen}\nIDs: {ids}"
    )
    print(f"OK: {ids}")


def main():
    if not CUENTA_SHORTCUT:
        notificar_telegram("❌ Photo ingestion failed: missing 'cuenta' in payload")
        sys.exit(1)
    if not FOTO_PATH:
        notificar_telegram("❌ Photo ingestion failed: missing 'foto_bucket_path' in payload")
        sys.exit(1)
    if not CATEGORIAS_RAW:
        notificar_telegram("❌ Photo ingestion failed: missing 'categorias' (preselected in the Shortcut) in payload")
        sys.exit(1)

    codigos_categoria = parsear_categorias(CATEGORIAS_RAW)
    if not codigos_categoria:
        notificar_telegram(f"❌ Photo ingestion failed: could not extract categories from: {CATEGORIAS_RAW!r}")
        sys.exit(1)

    payload = {"cuenta": CUENTA_SHORTCUT, "categorias": codigos_categoria, "foto_bucket_path": FOTO_PATH}

    try:
        filas_insertadas, etiquetas, comercio, fecha = procesar_foto(CUENTA_SHORTCUT, codigos_categoria, FOTO_PATH)
    except Exception as e:
        id_pendiente = guardar_registro_pendiente(
            "gasto_foto", payload, foto_bucket_path=FOTO_PATH, error_detalle=str(e)
        )
        notificar_telegram(f"❌ Photo ingestion failed ({id_pendiente}): {e}\n{NOTA_PENDIENTE}")
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    borrar_registros_pendientes_de_foto(FOTO_PATH)
    notificar_exito(filas_insertadas, etiquetas, comercio, fecha)


if __name__ == "__main__":
    main()
