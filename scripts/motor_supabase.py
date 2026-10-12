# -*- coding: utf-8 -*-
"""
Shared helpers for every ingestion script: resolve data against Supabase,
notify through Telegram and call the vision model (Qwen / DashScope).
It holds no business logic of any particular ingestion type: that lives in
each script (ingesta_estandarizada, ingesta_dinamica, ingesta_foto).
"""
import base64
import json
import os
import time
import unicodedata

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Per-user settings (GitHub repository variables, optional).
TZ_SISTEMA = os.environ.get("TZ_SISTEMA") or "Europe/Madrid"
CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL") or "€"

REST_HEADERS = {
    "apikey": SERVICE_KEY,
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
# Legacy service_role keys are JWTs and go in Authorization too. The new
# "sb_secret_..." keys are opaque: they only travel in the apikey header.
if not SERVICE_KEY.startswith("sb_secret_"):
    REST_HEADERS["Authorization"] = f"Bearer {SERVICE_KEY}"


def notificar_telegram(texto):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": texto}, timeout=10)
    except requests.RequestException:
        pass  # a Telegram failure must never hide the original error


def normalizar(texto):
    """Lowercase, accent-free, collapsed whitespace - done by code, not by the user.
    Tolerates how things are really written ("Pechuga de POLLO" matches the
    keyword "pollo"). Shared by the dynamic-expense matcher and the photo matcher."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().split())


SIGNO_POR_TIPO_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "signo_por_tipo.json")
with open(SIGNO_POR_TIPO_PATH, encoding="utf-8") as _f:
    _SIGNO_POR_TIPO = json.load(_f)


def resolver_signo(tipo):
    """Returns +1/-1 from config/signo_por_tipo.json for a category 'tipo'
    (ingreso, gasto, ...), or None if that type cannot be recorded in a
    single row (e.g. 'traspaso' needs 2 linked rows)."""
    return _SIGNO_POR_TIPO.get(tipo)


def resolver_categoria(codigo_categoria, fecha):
    """Returns {id_categoria, tipo, glosa} of the version valid on 'fecha',
    or None when no version is valid for that code + date."""
    url = f"{SUPABASE_URL}/rest/v1/categorias"
    params = {
        "codigo_categoria": f"eq.{codigo_categoria}",
        "fecha_inicio": f"lte.{fecha}",
        "or": f"(fecha_fin.is.null,fecha_fin.gte.{fecha})",
        "select": "id_categoria,tipo,glosa",
    }
    r = requests.get(url, headers=REST_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    filas = r.json()
    return filas[0] if filas else None


def resolver_id_cuenta_por_nombre(nombre_cuenta):
    """Returns the id_cuenta whose nombre_cuenta matches exactly, or None."""
    url = f"{SUPABASE_URL}/rest/v1/cuentas"
    params = {"nombre_cuenta": f"eq.{nombre_cuenta}", "select": "id_cuenta"}
    r = requests.get(url, headers=REST_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    filas = r.json()
    return filas[0]["id_cuenta"] if filas else None


def resolver_nombre_etiqueta_por_id(id_etiqueta):
    """Returns the nombre_etiqueta whose id_etiqueta matches exactly, or None."""
    url = f"{SUPABASE_URL}/rest/v1/etiquetas"
    params = {"id_etiqueta": f"eq.{id_etiqueta}", "select": "nombre_etiqueta"}
    r = requests.get(url, headers=REST_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    filas = r.json()
    return filas[0]["nombre_etiqueta"] if filas else None


def insertar_filas(filas):
    """Atomic POST (one single INSERT statement) of 1-N rows. Returns the raw
    requests response; the caller decides how to handle an error."""
    url = f"{SUPABASE_URL}/rest/v1/seguimiento_efectivo"
    return requests.post(url, headers=REST_HEADERS, json=filas, timeout=15)


def listar_objetos_storage(bucket):
    """Returns the objects of a bucket (each with 'name' and 'created_at',
    among other fields) as Supabase Storage exposes them."""
    url = f"{SUPABASE_URL}/storage/v1/object/list/{bucket}"
    body = {"prefix": "", "limit": 1000, "sortBy": {"column": "created_at", "order": "asc"}}
    r = requests.post(url, headers=REST_HEADERS, json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def borrar_objetos_storage(bucket, nombres):
    """Deletes a list of objects (by name, relative to the bucket) from
    Supabase Storage in one batch. Returns the raw requests response."""
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}"
    return requests.delete(url, headers=REST_HEADERS, json={"prefixes": nombres}, timeout=15)


NOTA_PENDIENTE = "Saved as pending: the nightly routine will process it tonight."


def guardar_registro_pendiente(origen, payload, foto_bucket_path=None, error_detalle=None):
    """Inserts a new pending record from a failure that just happened. It is
    born with estado='pendiente'; the nightly Claude routine resolves it and
    marks it 'procesado', and the daily GitHub purge deletes it. Returns the
    id_pendiente."""
    url = f"{SUPABASE_URL}/rest/v1/registros_pendientes"
    body = {
        "origen": origen,
        "payload": payload,
        "foto_bucket_path": foto_bucket_path,
        "error_detalle": error_detalle,
    }
    r = requests.post(url, headers=REST_HEADERS, json=[body], timeout=15)
    r.raise_for_status()
    return r.json()[0]["id_pendiente"]


def listar_fotos_pendientes_de_borrado():
    """Storage paths still referenced by unprocessed registros_pendientes
    (origen gasto_foto). limpieza_recibos.py uses it to never delete a photo
    the system still needs; the photo of an already processed pending can expire."""
    url = f"{SUPABASE_URL}/rest/v1/registros_pendientes"
    params = {"origen": "eq.gasto_foto", "estado": "eq.pendiente", "select": "foto_bucket_path"}
    r = requests.get(url, headers=REST_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return {fila["foto_bucket_path"] for fila in r.json() if fila["foto_bucket_path"]}


def borrar_registros_pendientes_de_foto(foto_bucket_path):
    """Deletes any gasto_foto pending associated with that path."""
    url = f"{SUPABASE_URL}/rest/v1/registros_pendientes"
    requests.delete(
        url,
        headers=REST_HEADERS,
        params={"foto_bucket_path": f"eq.{foto_bucket_path}", "origen": "eq.gasto_foto"},
        timeout=15,
    )


# --- Vision AI: Qwen through DashScope (OpenAI-compatible endpoint) ---
# QWEN_BASE_URL (the compatible-mode URL of your workspace) is a GitHub Actions
# secret. The MODEL is a parameter here in the script (not a secret). Options:
# qwen3-vl-flash (cheapest) or qwen3-vl-plus (more capable). The photo prompt is
# designed so that flash performs well: a numbered menu limited to the
# categories chosen in the Shortcut, a glossary enforced in code and amount
# verification against the receipt TOTAL.
QWEN_BASE_URL = (os.environ.get("QWEN_BASE_URL") or "").rstrip("/")
MODELO_QWEN = "qwen3-vl-flash"

MAX_INTENTOS_QWEN = 3    # total attempts (1 initial + 2 retries)
ESPERA_QWEN_5XX_SEG = 5  # 5xx = servers saturated
ESPERA_QWEN_429_SEG = 20  # 429 = rate limit


def _parsear_json_qwen(texto):
    """Parses the JSON the model returns, tolerating markdown fences
    (```json ... ```) or text around it."""
    t = (texto or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip()
    candidatos = [t]
    if "{" in t and "}" in t:
        candidatos.append(t[t.find("{"): t.rfind("}") + 1])
    for candidato in candidatos:
        try:
            return json.loads(candidato)
        except json.JSONDecodeError:
            continue
    raise RuntimeError(f"Qwen did not return valid JSON: {texto}")


def llamar_qwen_json(prompt, imagen_bytes=None, api_key=None, sistema=None):
    """Calls Qwen (DashScope, OpenAI-compatible /chat/completions endpoint).
    'sistema' (optional) is sent as the system message with the rules; 'prompt'
    is the user instruction and the image (optional) goes before the text, as
    Qwen-VL recommends. temperature=0: reading receipts, not creativity.
    Returns the parsed JSON. Raises RuntimeError with a clear message on failure.

    Retries on transient codes (5xx and 429); any other code fails right away.
    The immediate retry is ONLY for the AI - Supabase is not retried (if it is
    down, the operation becomes a pending record, by design)."""
    if not QWEN_BASE_URL:
        raise RuntimeError("QWEN_BASE_URL is missing from the environment (DashScope compatible-mode endpoint)")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is missing from the environment")

    url = f"{QWEN_BASE_URL}/chat/completions"
    content = []
    if imagen_bytes is not None:
        b64 = base64.b64encode(imagen_bytes).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "system", "content": sistema}] if sistema else []
    messages.append({"role": "user", "content": content})

    body = {"model": MODELO_QWEN, "messages": messages, "temperature": 0}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    r = None
    for intento in range(1, MAX_INTENTOS_QWEN + 1):
        r = requests.post(url, headers=headers, json=body, timeout=90)
        if r.ok or intento == MAX_INTENTOS_QWEN:
            break
        if r.status_code in (500, 502, 503, 504):
            time.sleep(ESPERA_QWEN_5XX_SEG)
            continue
        if r.status_code == 429:
            time.sleep(ESPERA_QWEN_429_SEG)
            continue
        break  # any other code: retrying will not fix it

    if not r.ok:
        raise RuntimeError(f"Qwen rejected the request ({r.status_code}): {r.text}")

    data = r.json()
    try:
        texto = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Unexpected Qwen response shape: {data}")

    return _parsear_json_qwen(texto)
