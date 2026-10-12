# -*- coding: utf-8 -*-
"""Converts a .shortcut (binary plist, or its JSON dump) into readable JSON:
actions with friendly names, variables resolved as {{Name}}, nested menus and
ifs, and secrets replaced by placeholders.

    python tools/shortcut_to_json.py <input> <output.json>

The input must be an unsigned property list (a signed .shortcut is an AEA
container; see tools/edit_shortcuts.py for how to get the plist out of it).
"""
import json
import plistlib
import re
import sys

REDACT = [
    (r"github_pat_[A-Za-z0-9_]+|ghp_[A-Za-z0-9]+", "{{GITHUB_PAT}}"),
    (r"sb_publishable_[A-Za-z0-9_-]+|sb_secret_[A-Za-z0-9_-]+", "{{SUPABASE_PUBLISHABLE_KEY}}"),
    (r"https://[a-z0-9]{20}\.supabase\.co", "https://{{SUPABASE_PROJECT_REF}}.supabase.co"),
    (r"repos/[^/\s\"]+/[^/\s\"]+/dispatches", "repos/{{GITHUB_OWNER}}/{{GITHUB_REPO}}/dispatches"),
]


def redact(s):
    for pat, rep in REDACT:
        s = re.sub(pat, rep, s)
    return s


FRIENDLY = {
    "list": "List", "choosefromlist": "Choose from list", "choosefrommenu": "Menu", "ask": "Ask for input",
    "gettext": "Text", "downloadurl": "Get contents of URL", "date": "Date", "takephoto": "Take photo",
    "image.convert": "Convert image", "convert": "Convert image", "number.random": "Random number",
    "random": "Random number", "setvariable": "Set variable", "appendvariable": "Add to variable",
    "text.combine": "Combine text", "combine": "Combine text", "repeat.each": "Repeat with each",
    "each": "Repeat with each", "conditional": "If", "dictionary": "Dictionary",
    "notification": "Notification", "format.date": "Format date",
}


def var(v):
    if not isinstance(v, dict):
        return str(v)
    t = v.get("Type")
    if t == "ActionOutput":
        return "{{" + v.get("OutputName", "output") + "}}"
    if t == "Variable":
        return "{{" + v.get("VariableName", "variable") + "}}"
    if t in ("CurrentDate", "Clipboard", "ExtensionInput", "Ask"):
        return "{{" + t + "}}"
    return "{{" + str(t) + "}}"


def val(x):
    """Flattens the serialized Shortcuts types into readable values."""
    if isinstance(x, dict):
        st = x.get("WFSerializationType")
        v = x.get("Value")
        if st == "WFTextTokenString":
            s = v.get("string", "")
            att = v.get("attachmentsByRange", {})
            for rng, a in sorted(att.items(), key=lambda kv: -int(re.findall(r"\d+", kv[0])[0])):
                pos = int(re.findall(r"\d+", rng)[0])
                s = s[:pos] + var(a) + s[pos + 1:]
            return redact(s)
        if st == "WFTextTokenAttachment":
            return var(v)
        if st == "WFDictionaryFieldValue":
            # nested dictionaries come wrapped twice: {"Value": {"WFDictionaryFieldValueItems": [...]}}
            while isinstance(v, dict) and "WFDictionaryFieldValueItems" not in v and "Value" in v:
                v = v["Value"]
            return {val(i.get("WFKey")): val(i.get("WFValue")) for i in v.get("WFDictionaryFieldValueItems", [])}
        if st == "WFArrayParameterState":
            return [val(i) for i in v]
        if st == "WFNumberSubstitutableState":
            return val(v)
        if st:
            return val(v)
        return {k: val(w) for k, w in x.items()}
    if isinstance(x, list):
        return [val(i) for i in x]
    return redact(x) if isinstance(x, str) else x


SKIP = {"UUID", "GroupingIdentifier", "WFControlFlowMode", "CustomOutputName", "ShowWhenRun"}


def convert(p):
    out, stack, n = [], [], 0
    for a in p["WFWorkflowActions"]:
        ident = a["WFWorkflowActionIdentifier"].replace("is.workflow.actions.", "")
        prm = a.get("WFWorkflowActionParameters", {})
        mode = prm.get("WFControlFlowMode")
        cur = stack[-1]["_branch"] if stack else out
        if mode == 1:  # new branch (menu option / else)
            blk = stack[-1]
            title = prm.get("WFMenuItemTitle", "Otherwise")
            blk["branches"].append({"option": val(title), "steps": []})
            blk["_branch"] = blk["branches"][-1]["steps"]
            continue
        if mode == 2:  # end of block
            stack.pop()
            continue
        n += 1
        step = {"step": n, "action": FRIENDLY.get(ident, ident)}
        if prm.get("CustomOutputName"):
            step["output"] = prm["CustomOutputName"]
        params = {k: val(v) for k, v in prm.items()
                  if k not in SKIP and k not in ("WFMenuItems", "WFMenuPrompt")}
        params = {re.sub(r"^WF", "", k): v for k, v in params.items()}
        # With a File/Form body, JSONValues is an unused leftover: the real body is RequestVariable
        if params.get("HTTPBodyType") in ("File", "Form"):
            params.pop("JSONValues", None)
        if params:
            step["parameters"] = params
        if mode == 0:
            if ident == "choosefrommenu":
                step["question"] = val(prm.get("WFMenuPrompt", ""))
                step["branches"] = []
                step["_branch"] = []
            else:
                step["branches"] = [{"option": "Per item", "steps": []}]
                step["_branch"] = step["branches"][0]["steps"]
            cur.append(step)
            stack.append(step)
            continue
        cur.append(step)

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items() if k != "_branch"}
        if isinstance(o, list):
            return [clean(i) for i in o]
        return o
    return clean(out)


def triggers(p):
    res = []
    for t in p.get("WFWorkflowTriggers", []):
        wallet = "WFWalletCards" in json.dumps(t, default=str)
        res.append({"type": t.get("WFTriggerIdentifier"), "wallet_cards": "{{WALLET_CARDS}}" if wallet else None})
    return res


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    raw = open(src, "rb").read()
    p = plistlib.loads(raw) if raw[:6] == b"bplist" else json.loads(raw)
    name = p.get("_name") or re.split(r"[\\/]", src)[-1].split(".")[0]
    doc = {
        "name": name,
        "minimum_ios_client_version": p.get("WFWorkflowMinimumClientVersionString"),
        "triggers": triggers(p),
        "actions": convert(p),
    }
    json.dump(doc, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(dst, "OK")
