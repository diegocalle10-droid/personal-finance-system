"""Convierte un .shortcut (binary plist o su volcado JSON) en un JSON legible:
acciones con nombre amigable, variables resueltas como {{Nombre}}, menus e if anidados,
y secretos sustituidos por placeholders. Uso: python shortcut_to_json.py <entrada> <salida.json>"""
import sys, json, re, plistlib

REDACT = [
    (r"github_pat_[A-Za-z0-9_]+|ghp_[A-Za-z0-9]+|\[GITHUB_PAT\]", "{{GITHUB_PAT}}"),
    (r"sb_publishable_[A-Za-z0-9_-]+|\[SB_PUBLISHABLE\]", "{{SUPABASE_PUBLISHABLE_KEY}}"),
    (r"https://[a-z0-9]{20}\.supabase\.co", "https://{{SUPABASE_PROJECT_REF}}.supabase.co"),
    (r"repos/[^/\s\"]+/[^/\s\"]+/dispatches", "repos/{{GITHUB_OWNER}}/{{GITHUB_REPO}}/dispatches"),
]
def redact(s):
    for pat, rep in REDACT: s = re.sub(pat, rep, s)
    return s

FRIENDLY = {"list":"Lista","choosefromlist":"Elegir de lista","choosefrommenu":"Menu","ask":"Pedir dato",
 "gettext":"Texto","downloadurl":"HTTP request","date":"Fecha","takephoto":"Tomar foto","convert":"Convertir imagen",
 "random":"Numero aleatorio","setvariable":"Definir variable","combine":"Combinar texto","each":"Repetir con cada",
 "conditional":"Si","dictionary":"Diccionario","notification":"Notificacion","format.date":"Formatear fecha","image.convert":"Convertir imagen","number.random":"Numero aleatorio"}

def var(v):
    if not isinstance(v, dict): return str(v)
    t = v.get("Type")
    if t == "ActionOutput": return "{{" + v.get("OutputName", "salida") + "}}"
    if t == "Variable": return "{{" + v.get("VariableName", "var") + "}}"
    if t in ("CurrentDate","Clipboard","ExtensionInput","Ask"): return "{{" + t + "}}"
    return "{{" + str(t) + "}}"

def val(x):
    """Aplana los tipos serializados de Shortcuts a valores legibles."""
    if isinstance(x, dict):
        st = x.get("WFSerializationType")
        v = x.get("Value")
        if st == "WFTextTokenString":
            s = v.get("string", ""); att = v.get("attachmentsByRange", {})
            for rng, a in sorted(att.items(), key=lambda kv: -int(re.findall(r"\d+", kv[0])[0])):
                pos = int(re.findall(r"\d+", rng)[0]); s = s[:pos] + var(a) + s[pos+1:]
            return redact(s)
        if st == "WFTextTokenAttachment": return var(v)
        if st == "WFDictionaryFieldValue":
            # Los diccionarios anidados vienen doblemente envueltos: {"Value": {"WFDictionaryFieldValueItems": [...]}}
            while isinstance(v, dict) and "WFDictionaryFieldValueItems" not in v and "Value" in v:
                v = v["Value"]
            return {val(i.get("WFKey")): val(i.get("WFValue")) for i in v.get("WFDictionaryFieldValueItems", [])}
        if st == "WFArrayParameterState": return [val(i) for i in v]
        if st == "WFNumberSubstitutableState": return val(v)
        if st: return val(v)
        return {k: val(w) for k, w in x.items()}
    if isinstance(x, list): return [val(i) for i in x]
    return redact(x) if isinstance(x, str) else x

SKIP = {"UUID","GroupingIdentifier","WFControlFlowMode","CustomOutputName","ShowWhenRun"}

def convert(p):
    out, stack, n = [], [], 0
    root = out
    for a in p["WFWorkflowActions"]:
        ident = a["WFWorkflowActionIdentifier"].replace("is.workflow.actions.", "")
        prm = a.get("WFWorkflowActionParameters", {})
        mode = prm.get("WFControlFlowMode")
        cur = stack[-1]["_branch"] if stack else root
        if mode == 1:  # nueva rama (opcion de menu / else)
            blk = stack[-1]; title = prm.get("WFMenuItemTitle", "Si no")
            blk["ramas"].append({"opcion": val(title), "pasos": []}); blk["_branch"] = blk["ramas"][-1]["pasos"]; continue
        if mode == 2: stack.pop(); continue  # fin de bloque
        n += 1
        step = {"paso": n, "accion": FRIENDLY.get(ident, ident)}
        if prm.get("CustomOutputName"): step["salida"] = prm["CustomOutputName"]
        params = {k: val(v) for k, v in prm.items() if k not in SKIP and k not in ("WFMenuItems","WFMenuPrompt")}
        params = {re.sub(r"^WF", "", k): v for k, v in params.items()}
        # Con cuerpo File/Form, JSONValues es un resto sin uso: el cuerpo real es RequestVariable
        if params.get("HTTPBodyType") in ("File", "Form"): params.pop("JSONValues", None)
        if params: step["parametros"] = params
        if mode == 0:
            if ident == "choosefrommenu": step["pregunta"] = val(prm.get("WFMenuPrompt", ""))
            step["ramas"] = []
            if ident != "choosefrommenu": step["ramas"].append({"opcion": "Si se cumple", "pasos": []}); step["_branch"] = step["ramas"][0]["pasos"]
            else: step["_branch"] = []
            cur.append(step); stack.append(step); continue
        cur.append(step)
    def clean(o):
        if isinstance(o, dict): return {k: clean(v) for k, v in o.items() if k != "_branch"}
        if isinstance(o, list): return [clean(i) for i in o]
        return o
    return clean(out)

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    raw = open(src, "rb").read()
    p = plistlib.loads(raw) if raw[:6] == b"bplist" else json.loads(raw)
    doc = {"nombre": p.get("_name") or src.rsplit("/",1)[-1].split(".")[0],
           "version_minima_ios_cliente": p.get("WFWorkflowMinimumClientVersionString"),
           "disparadores": [{"tipo": t.get("WFTriggerIdentifier"),
                             "tarjetas_wallet": "{{TUS_TARJETAS_WALLET}}" if "WFWalletCards" in json.dumps(t) else None}
                            for t in p.get("WFWorkflowTriggers", [])],
           "acciones": convert(p)}
    json.dump(doc, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(dst, "OK")
