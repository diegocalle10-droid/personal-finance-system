# -*- coding: utf-8 -*-
"""Turn your own exported Shortcuts into the public, English-only templates.

    python tools/edit_shortcuts.py <dir with Compras.shortcut Gasto_fijo.shortcut Manufinanza.shortcut> <out dir>

Inputs are *unsigned* property lists (what a .shortcut file contains once the
signature container is removed). What it does:

  * replaces every secret by a placeholder (GitHub token, Supabase key, URLs)
  * replaces every personal list item by a numbered placeholder
  * translates every prompt, menu title and variable name to English
  * Gasto_fijo: fills an empty menu slot, adds the "Credit card payment" option
  * Manufinanza: removes the date question (records are stamped with the system date)
  * validates the result (menus consistent, variable references resolve)

The output is unsigned. iOS only imports signed Shortcuts: sign on a Mac with
    shortcuts sign --mode anyone --input X.shortcut --output X.signed.shortcut
"""
import copy
import json
import os
import plistlib
import re
import sys
import uuid

OBJ = "￼"

GITHUB_URL = "https://api.github.com/repos/{{GITHUB_OWNER}}/{{GITHUB_REPO}}/dispatches"
STORAGE_PREFIX = "https://{{SUPABASE_PROJECT_REF}}.supabase.co/storage/v1/object/"

PROMPTS = {
    "¿Cuál es la fecha del pago?": "What is the payment date?",
    "¿How much did you pay?": "How much did you pay?",
    "¿Which account are used?": "Which account is used?",
    "¿Which account are you paying from?": "Which account are you paying from?",
    "¿Why are you saving this?": "Why are you saving this?",
    "¿Why are you withdrawing this?": "Why are you withdrawing this?",
    "¿What are you logging?": "What are you logging?",
    "¿Que vas a registrar?": "What are you logging?",
    "¿Cuanto dinero vas a ingresar?": "How much money are you adding?",
    "Descripcion del ingreso": "Income description",
    "detalles del ingreso": "Income details",
    "Selecciona una cuenta": "Select an account",
    "Selecciona una categoria de gasto": "Select an expense category",
    "¿Tienes el recibo de tu gasto?": "Do you have the receipt?",
    "Fecha del movimiento": "Movement date",
}
PREFIXES = [  # (old prefix, new prefix) for prompts that end in a variable
    ("Monto para ", "Amount for "),
    ("Descripción para ", "Description for "),
    ("comentario o detalles", "Comment or details for "),
    ("Nombre del gasto", "Expense name for "),
    ("Comentario del gasto ", "Expense comment for "),
]
MENU_TITLES = {
    "Ingreso": "Income", "Gasto": "Expense", "Si": "Yes", "Sí": "Yes", "No": "No",
    "Aporte de ahorro": "Savings deposit", "Retiro de ahorro": "Savings withdrawal",
    "Pago de tarjeta": "Credit card payment",
}
NAMES = {  # variable / output names
    "Cuenta": "Account", "Categorias": "Categories", "Lineas": "Lines",
    "Ítems seleccionados": "Selected Items", "Texto": "Text", "Solicitar entrada": "Ask for Input",
    "Entrada proporcionada": "Provided Input", "Elemento seleccionado": "Selected Item",
    "Elemento de repetición": "Repeat Item", "Texto combinado": "Combined Text",
    "Fecha con formato": "Formatted Date", "Imagen convertida": "Converted Image",
    "Número aleatorio": "Random Number", "Diccionario": "Dictionary", "Lista": "List",
    "Foto": "Photo",
}
KEY_RENAMES = {"ahorro_aporte": "savings_deposit", "ahorro_retiro": "savings_withdrawal",
               "pago_tarjeta": "credit_card_payment"}
NAME_KEYS = {"CustomOutputName", "OutputName", "VariableName", "WFVariableName"}
SECRET = re.compile(r"github_pat_[A-Za-z0-9_]+|ghp_[A-Za-z0-9]+|sb_(publishable|secret)_[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]{20,}")


# ---------------------------------------------------------------- text tokens
def parse_range(key):
    a, b = re.findall(r"\d+", key)
    return int(a), int(b)


def get_text(value):
    """-> (string, attachments{pos: dict}) for a plain str or a WFTextTokenString."""
    if isinstance(value, str):
        return value, {}
    v = value["Value"]
    att = {parse_range(k)[0]: a for k, a in (v.get("attachmentsByRange") or {}).items()}
    return v["string"], att


def make_text(string, att):
    if not att:
        return string
    return {"Value": {"string": string,
                      "attachmentsByRange": {"{%d, 1}" % p: a for p, a in att.items()}},
            "WFSerializationType": "WFTextTokenString"}


def replace_prefix(value, old, new):
    s, att = get_text(value)
    if not s.startswith(old):
        return value
    d = len(new) - len(old)
    return make_text(new + s[len(old):], {p + d: a for p, a in att.items()})


def translate_prompt(value):
    s, att = get_text(value)
    if not att and s in PROMPTS:
        return PROMPTS[s]
    for old, new in PREFIXES:
        if s.startswith(old):
            return replace_prefix(value, old, new)
    return value


# ------------------------------------------------------------------- walkers
def walk(node, fn):
    if isinstance(node, dict):
        for k in list(node):
            node[k] = fn(k, node[k]) if not isinstance(node[k], (dict, list)) else node[k]
            if isinstance(node[k], (dict, list)):
                walk(node[k], fn)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, (dict, list)):
                walk(v, fn)


def rename_names(root):
    def fn(k, v):
        if k in NAME_KEYS and isinstance(v, str):
            return NAMES.get(v, v)
        return v
    walk(root, fn)


def scrub_secrets(root):
    def fn(k, v):
        if isinstance(v, str) and SECRET.search(v):
            return SECRET.sub("{{SECRET}}", v)
        return v
    walk(root, fn)


def params(a):
    return a["WFWorkflowActionParameters"]


def ident(a):
    return a["WFWorkflowActionIdentifier"].replace("is.workflow.actions.", "")


# --------------------------------------------------------------- HTTP header
def header_items(p):
    return p["WFHTTPHeaders"]["Value"]["WFDictionaryFieldValueItems"]


def set_header(p, name, value):
    for it in header_items(p):
        if get_text(it["WFKey"])[0].lower() == name.lower():
            it["WFValue"] = make_text(value, {})
            return
    header_items(p).append({"WFKey": make_text(name, {}), "WFItemType": 0, "WFValue": make_text(value, {})})


def header_value(p, name):
    for it in header_items(p):
        if get_text(it["WFKey"])[0].lower() == name.lower():
            return get_text(it["WFValue"])[0]
    return None


def fix_http(a):
    p = params(a)
    storage = header_value(p, "apikey") is not None or (header_value(p, "Content-Type") or "").startswith("image")
    if storage:
        s, att = get_text(p.get("WFURL", ""))
        if att:  # keep the variable, put the endpoint in front of it
            pos = min(att)
            p["WFURL"] = make_text(STORAGE_PREFIX + OBJ, {len(STORAGE_PREFIX): att[pos]})
        else:
            p["WFURL"] = STORAGE_PREFIX
        set_header(p, "apikey", "{{SUPABASE_PUBLISHABLE_KEY}}")
        set_header(p, "Authorization", "Bearer {{SUPABASE_PUBLISHABLE_KEY}}")
    else:
        p["WFURL"] = GITHUB_URL
        set_header(p, "Authorization", "Bearer {{GITHUB_PAT}}")


# ------------------------------------------------------------------ placeholders
def placeholders(actions, name):
    fixed_label = fixed_key = 0
    for a in actions:
        i = ident(a)
        p = params(a)
        if i == "downloadurl":
            fix_http(a)
        elif i == "list" and isinstance(p.get("WFItems"), list):
            items = p["WFItems"]
            text = " ".join(str(x) for x in items)
            if re.search(r"cuenta|efectivo|account|cash", text, re.I):
                p["WFItems"] = ["{{ACCOUNT_%d}}" % (n + 1) for n in range(len(items))]
            elif re.search(r"categor", text, re.I):
                p["WFItems"] = ["{{CATEGORY_%d}}" % (n + 1) for n in range(len(items))]
        elif i == "gettext":
            t = p["WFTextActionText"]
            s, att = get_text(t)
            if not att and re.fullmatch(r"comple\w*", s.strip(), re.I):
                fixed_key += 1
                p["WFTextActionText"] = "{{FIXED_EXPENSE_%d_KEY}}" % fixed_key
            elif not att and s.strip() in ("other_income", "ingresos_varios"):
                p["WFTextActionText"] = "{{INCOME_CATEGORY_CODE}}"
            elif not att and s.strip() in KEY_RENAMES:
                p["WFTextActionText"] = KEY_RENAMES[s.strip()]
    return fixed_label, fixed_key


def translate_all(actions):
    for a in actions:
        i = ident(a)
        p = params(a)
        for key in ("WFAskActionPrompt", "WFChooseFromListActionPrompt", "WFMenuPrompt"):
            if key in p:
                p[key] = translate_prompt(p[key])
        if i == "choosefrommenu":
            if "WFMenuItems" in p:
                p["WFMenuItems"] = [MENU_TITLES.get(t, t) if isinstance(t, str) else t for t in p["WFMenuItems"]]
            if isinstance(p.get("WFMenuItemTitle"), str):
                p["WFMenuItemTitle"] = MENU_TITLES.get(p["WFMenuItemTitle"], p["WFMenuItemTitle"])


# ---------------------------------------------------------------- Gasto_fijo
def new_uuid():
    return str(uuid.uuid4()).upper()


def remap(obj, mapping):
    if isinstance(obj, dict):
        return {k: remap(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [remap(v, mapping) for v in obj]
    if isinstance(obj, str):
        return mapping.get(obj, obj)
    return obj


def clone_group(actions):
    """Deep copy with fresh UUIDs; internal references follow the new ids."""
    mapping = {}
    for a in actions:
        u = params(a).get("UUID")
        if u:
            mapping[u] = new_uuid()
    return [remap(copy.deepcopy(a), mapping) for a in actions], mapping


def menu_bounds(actions):
    """-> (menu_header_index, [item start indexes], end_index) of the first menu."""
    start = next(i for i, a in enumerate(actions)
                 if ident(a) == "choosefrommenu" and params(a).get("WFControlFlowMode") == 0)
    gid = params(actions[start])["GroupingIdentifier"]
    items, end = [], None
    for i in range(start + 1, len(actions)):
        p = params(actions[i])
        if ident(actions[i]) == "choosefrommenu" and p.get("GroupingIdentifier") == gid:
            if p.get("WFControlFlowMode") == 1:
                items.append(i)
            elif p.get("WFControlFlowMode") == 2:
                end = i
                break
    return start, items, end


def fill_empty_slots(actions):
    """A fixed-expense slot with no actions copies the previous slot (new key)."""
    start, items, end = menu_bounds(actions)
    bounds = items + [end]
    out = list(actions[:start + 1])
    prev = None
    for n, s in enumerate(items):
        body = actions[s + 1:bounds[n + 1]]
        head = actions[s]
        if not body and prev is not None:
            body, _ = clone_group(prev)
        out.append(head)
        out.extend(body)
        if body:
            prev = body
    out.append(actions[end])
    out.extend(actions[end + 1:])
    return out


def number_slots(actions):
    """Menu items / keys that are still 'comple…' get numbered placeholders."""
    start, items, end = menu_bounds(actions)
    n = 0
    for s in items:
        t = params(actions[s]).get("WFMenuItemTitle", "")
        if re.fullmatch(r"comple\w*", t.strip(), re.I) or re.fullmatch(r"\{\{FIXED_EXPENSE_\d+_LABEL\}\}", t):
            n += 1
            params(actions[s])["WFMenuItemTitle"] = "{{FIXED_EXPENSE_%d_LABEL}}" % n
    # menu header list: same order as items
    titles = [params(actions[s])["WFMenuItemTitle"] for s in items]
    params(actions[start])["WFMenuItems"] = titles
    # keys: every gettext still holding a key placeholder or comple… is renumbered in order
    k = 0
    bounds = items + [end]
    for idx, s in enumerate(items):
        title = params(actions[s])["WFMenuItemTitle"]
        if not title.startswith("{{FIXED_EXPENSE_"):
            continue
        k += 1
        for a in actions[s + 1:bounds[idx + 1]]:
            if ident(a) == "gettext":
                txt = get_text(params(a)["WFTextActionText"])[0]
                if re.fullmatch(r"comple\w*", txt.strip(), re.I) or txt.startswith("{{FIXED_EXPENSE_"):
                    params(a)["WFTextActionText"] = "{{FIXED_EXPENSE_%d_KEY}}" % k
                break


def payload_items(dispatch):
    p = params(dispatch)
    top = p["WFJSONValues"]["Value"]["WFDictionaryFieldValueItems"]
    cp = next(it for it in top if get_text(it["WFKey"])[0] == "client_payload")
    return cp["WFValue"]["Value"]["Value"]["WFDictionaryFieldValueItems"]


def savings_prompts(actions):
    """Clearer question for the two structural savings options."""
    start, items, end = menu_bounds(actions)
    bounds = items + [end]
    for n, i in enumerate(items):
        title = params(actions[i])["WFMenuItemTitle"]
        prompt = {"Savings deposit": "How much are you saving?",
                  "Savings withdrawal": "How much are you withdrawing?"}.get(title)
        if not prompt:
            continue
        for a in actions[i + 1:bounds[n + 1]]:
            if ident(a) == "ask" and params(a).get("WFInputType") == "Number":
                params(a)["WFAskActionPrompt"] = prompt


def add_card_payment(actions):
    start, items, end = menu_bounds(actions)
    titles = [params(actions[s])["WFMenuItemTitle"] for s in items]
    if "Credit card payment" in titles or "Pago de tarjeta" in titles:
        return actions
    dep = next(s for s in items if params(actions[s])["WFMenuItemTitle"] in ("Savings deposit", "Aporte de ahorro"))
    nxt = items[items.index(dep) + 1]
    group = actions[dep:nxt]  # item start, text, ask, list, choose, ask(why), dispatch
    group, mapping = clone_group(group)
    kinds = [ident(a) for a in group]
    assert kinds == ["choosefrommenu", "gettext", "ask", "list", "choosefromlist", "ask", "downloadurl"], kinds
    head, text, ask_amount, lst, choose, ask_why, dispatch = group
    params(head)["WFMenuItemTitle"] = "Credit card payment"
    params(text)["WFTextActionText"] = "credit_card_payment"
    params(choose)["WFChooseFromListActionPrompt"] = "Which account are you paying from?"
    # second list + choice: the credit card being paid
    lst2, m2 = clone_group([lst, choose])
    params(lst2[0])["WFItems"] = ["{{CREDIT_CARD_1}}"]
    params(lst2[1])["WFChooseFromListActionPrompt"] = "Which card are you paying?"
    card_choice = params(lst2[1])["UUID"]
    pay = payload_items(dispatch)
    # drop 'comentario', add 'cuenta_destino' pointing at the card choice
    pay[:] = [it for it in pay if get_text(it["WFKey"])[0] != "comentario"]
    cuenta = next(it for it in pay if get_text(it["WFKey"])[0] == "cuenta")
    dest = copy.deepcopy(cuenta)
    dest["WFKey"] = make_text("cuenta_destino", {})
    s, att = get_text(dest["WFValue"])
    att[0] = dict(att[0], OutputUUID=card_choice)
    dest["WFValue"] = make_text(s, att)
    pay.append(dest)
    new_group = [head, text, ask_amount, lst, choose, lst2[0], lst2[1], dispatch]
    out = actions[:nxt] + new_group + actions[nxt:]
    # menu header: same titles, same order as the items
    start, items, end = menu_bounds(out)
    params(out[start])["WFMenuItems"] = [params(out[i])["WFMenuItemTitle"] for i in items]
    return out


def drop_dict_items(node, dead):
    """Remove dictionary entries (JSON body builders) that read a removed action."""
    def uses(o):
        if isinstance(o, dict):
            return o.get("OutputUUID") in dead or any(uses(v) for v in o.values())
        if isinstance(o, list):
            return any(uses(v) for v in o)
        return False
    if isinstance(node, dict):
        items = node.get("WFDictionaryFieldValueItems")
        if isinstance(items, list):
            node["WFDictionaryFieldValueItems"] = [it for it in items if not uses(it)]
        for v in node.values():
            drop_dict_items(v, dead)
    elif isinstance(node, list):
        for v in node:
            drop_dict_items(v, dead)


# ---------------------------------------------------------------- Manufinanza
def strip_date(actions):
    """Remove 'ask date' + 'format date' and every use of the formatted date."""
    if len(actions) > 1 and ident(actions[0]) == "ask" and ident(actions[1]) == "format.date":
        dead = {params(actions[1])["UUID"], params(actions[0])["UUID"]}
        actions = actions[2:]
    else:
        return actions
    for a in actions:
        for k, v in list(params(a).items()):
            if isinstance(v, dict) and isinstance(v.get("Value"), dict) and "string" in v["Value"]:
                s, att = get_text(v)
                bad = [p for p, x in att.items() if x.get("OutputUUID") in dead]
                for pos in sorted(bad, reverse=True):
                    m = re.search(r'"fecha"\s*:\s*"' + OBJ + r'"\s*,?', s[:pos + 2])
                    # locate the '"fecha":"￼",' fragment ending at this attachment
                    frag = re.compile(r'"fecha"\s*:\s*"' + OBJ + r'"\s*,?')
                    hit = None
                    for mm in frag.finditer(s):
                        if mm.start() < pos < mm.end():
                            hit = mm
                    if hit is None:
                        continue
                    removed = hit.end() - hit.start()
                    s = s[:hit.start()] + s[hit.end():]
                    att = {(q if q < hit.start() else q - removed): x for q, x in att.items() if q != pos}
                params(a)[k] = make_text(s, att)
    drop_dict_items(actions, dead)
    return actions


# ------------------------------------------------------------------ validate
def validate(pl, name):
    actions = pl["WFWorkflowActions"]
    defined = {params(a)["UUID"] for a in actions if "UUID" in params(a)}
    problems = []

    def refs(o):
        if isinstance(o, dict):
            if "OutputUUID" in o:
                yield o["OutputUUID"]
            for v in o.values():
                yield from refs(v)
        elif isinstance(o, list):
            for v in o:
                yield from refs(v)
    for u in refs(actions):
        if u not in defined:
            problems.append("dangling reference " + u)
    groups = {}
    for a in actions:
        p = params(a)
        if "GroupingIdentifier" in p:
            groups.setdefault(p["GroupingIdentifier"], []).append(p.get("WFControlFlowMode"))
    for g, modes in groups.items():
        if modes.count(0) != 1 or modes.count(2) != 1:
            problems.append("unbalanced control-flow group " + g)
    for a in actions:
        p = params(a)
        if ident(a) == "choosefrommenu" and p.get("WFControlFlowMode") == 0:
            items = [params(x)["WFMenuItemTitle"] for x in actions
                     if ident(x) == "choosefrommenu" and params(x).get("GroupingIdentifier") == p["GroupingIdentifier"]
                     and params(x).get("WFControlFlowMode") == 1]
            if items != list(p["WFMenuItems"]):
                problems.append("menu titles differ from header: %r vs %r" % (items, p["WFMenuItems"]))
    text = json.dumps(pl, ensure_ascii=False, default=lambda o: "<bytes>")
    if SECRET.search(text):
        problems.append("secret-like value left")
    if re.search(r"comple(tar|ar)", text, re.I):
        problems.append("Spanish placeholder left")
    return problems


def process(path_in, path_out, name):
    pl = plistlib.load(open(path_in, "rb"))
    actions = pl["WFWorkflowActions"]
    scrub_secrets(actions)
    for t in pl.get("WFWorkflowTriggers", []):  # personal Wallet pass ids: the user picks the cards again
        sp = t.get("WFTriggerSerializedParameters", {})
        if "WFWalletCards" in sp:
            sp["WFWalletCards"] = []
    for a in actions:
        if ident(a) == "format.date" and "WFLocale" in params(a):
            params(a)["WFLocale"] = "en"
    if name == "Manufinanza":
        actions = strip_date(actions)
    if name == "Gasto_fijo":
        actions = fill_empty_slots(actions)
    placeholders(actions, name)
    translate_all(actions)
    if name == "Gasto_fijo":
        number_slots(actions)
        actions = add_card_payment(actions)
        savings_prompts(actions)
    rename_names(actions)
    # restore real placeholders removed by the secret scrubber
    pl["WFWorkflowActions"] = actions
    problems = validate(pl, name)
    with open(path_out, "wb") as f:
        plistlib.dump(pl, f, fmt=plistlib.FMT_BINARY)
    return problems


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    bad = False
    for n in ("Manufinanza", "Compras", "Gasto_fijo"):
        probs = process(os.path.join(src, n + ".shortcut"), os.path.join(dst, n + ".shortcut"), n)
        print(n, "OK" if not probs else "PROBLEMS: " + "; ".join(probs))
        bad = bad or bool(probs)
    sys.exit(1 if bad else 0)
