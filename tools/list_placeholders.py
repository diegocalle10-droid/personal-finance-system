# -*- coding: utf-8 -*-
"""Lists every {{PLACEHOLDER}} in shortcuts/*.json with the shortcut and step
where it appears. Placeholders written in CAPS are values YOU fill in; the
lower-case / mixed-case ones ({{Selected Item}}, {{Ask for Input}}...) are
Shortcuts magic variables and are not touched."""
import glob
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PH = re.compile(r"\{\{([A-Z][A-Z0-9_]+)\}\}")


def scan(node, path, found, shortcut):
    if isinstance(node, dict):
        paso = node.get("paso", path)
        for v in node.values():
            scan(v, paso, found, shortcut)
    elif isinstance(node, list):
        for v in node:
            scan(v, path, found, shortcut)
    elif isinstance(node, str):
        for name in PH.findall(node):
            found[name].add((shortcut, path))


def placeholders():
    found = defaultdict(set)
    for p in sorted(glob.glob(os.path.join(ROOT, "shortcuts", "*.json"))):
        scan(json.load(open(p, encoding="utf-8")), "-", found, os.path.basename(p)[:-5])
    return found


if __name__ == "__main__":
    for name, where in sorted(placeholders().items()):
        steps = sorted({f"{s}#{p}" for s, p in where})
        print(f"{name}: {len(where)} use(s): {', '.join(steps[:6])}{' ...' if len(steps) > 6 else ''}")
    sys.exit(0)
