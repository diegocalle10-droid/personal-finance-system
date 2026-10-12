# -*- coding: utf-8 -*-
"""Generates the 4 portfolio infographics (SVG, 1536x1024) of the project.

    python tools/make_portfolio_slides.py [output_dir]

Pure Python, no dependencies. Render to PNG with any browser, e.g.
    msedge --headless --screenshot=out.png --window-size=1536,1024 file:///.../slide-1-overview.svg
"""
import os
import sys
from xml.sax.saxutils import escape

W, H = 1536, 1024
SANS = "'Segoe UI','Inter','Helvetica Neue',Arial,sans-serif"
SCRIPT = "'Segoe Script','Brush Script MT','Lucida Handwriting',cursive"

NAVY_TXT = "#14206B"
CYAN = "#22D3EE"
PURPLE = "#8B5CF6"
MINT = "#3ECF8E"
ORANGE = "#E08A5F"
ROSE = "#FB7185"
AMBER = "#FBBF24"
MUTED = "#9FB4E8"


# ------------------------------------------------------------------ primitives
def T(x, y, s, size=18, weight=400, fill="#FFFFFF", anchor="start", opacity=1.0, ls=0, family=None, rot=None, style=""):
    fam = family or SANS
    tr = f' transform="rotate({rot} {x} {y})"' if rot is not None else ""
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" opacity="{opacity}" letter-spacing="{ls}"{tr} {style}>{escape(s)}</text>')


def lines(x, y, rows, size=17, gap=None, **kw):
    gap = gap or size * 1.38
    return "".join(T(x, y + i * gap, r, size, **kw) for i, r in enumerate(rows))


def rect(x, y, w, h, r=14, fill="none", stroke="none", sw=1.2, opacity=1.0, extra=""):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" opacity="{opacity}" {extra}/>')


def glass(x, y, w, h, r=16, strong=False):
    return rect(x, y, w, h, r, fill="url(#glassFill)" if not strong else "url(#glassStrong)",
                stroke="#6EA8FF", sw=1.1, opacity=1.0)


def light(x, y, w, h, r=12, tone="lav"):
    fill = {"lav": "#E9EAFF", "cyan": "#CFF3FF", "mint": "#D9F8EA", "rose": "#FFE1E6", "amber": "#FFF1CC"}[tone]
    return rect(x, y, w, h, r, fill=fill, stroke="#FFFFFF", sw=1, extra='filter="url(#soft)"')


def arrow(x1, y1, x2, y2, color="#8FB4FF", sw=2.2, dash=None, head=True):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = ' marker-end="url(#arrowHead)"' if head else ""
    if color != "#8FB4FF":
        m = ' marker-end="url(#arrowRose)"' if color == ROSE else ' marker-end="url(#arrowHead)"'
    return f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" stroke-width="{sw}" fill="none"{d}{m}/>'


def path_arrow(d, color="#8FB4FF", sw=2.2, dash=None):
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    m = ' marker-end="url(#arrowRose)"' if color == ROSE else ' marker-end="url(#arrowHead)"'
    return f'<path d="{d}" stroke="{color}" stroke-width="{sw}" fill="none"{ds}{m} stroke-linejoin="round"/>'


def chip(x, y, label, w=None, fill="#13306F", stroke="#6EA8FF", color="#DCE8FF", size=15):
    w = w or int(len(label) * size * 0.56 + 26)
    return (rect(x, y, w, 30, 15, fill=fill, stroke=stroke, sw=1) +
            T(x + w / 2, y + 20.5, label, size, 600, color, "middle"))


# ------------------------------------------------------------------ icon glyphs (24x24, stroke)
GLYPHS = {
    "phone": '<rect x="7" y="2" width="10" height="20" rx="2.5"/><path d="M11 18.5h2"/>',
    "database": '<ellipse cx="12" cy="5.5" rx="7" ry="2.8"/><path d="M5 5.5v13c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8v-13"/><path d="M5 12c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "shield": '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
    "gear": '<circle cx="12" cy="12" r="3.6"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "send": '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>',
    "camera": '<rect x="3" y="7" width="18" height="13" rx="2.5"/><circle cx="12" cy="13.5" r="3.5"/><path d="M8 7l1.5-3h5L16 7"/>',
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    "check": '<path d="M5 12l4.5 4.5L19 7"/>',
    "doc": '<path d="M6 2h8l5 5v15H6z"/><path d="M14 2v5h5M9 13h7M9 17h7"/>',
    "spark": '<path d="M12 2l2.2 6.3L21 10.5l-6.8 2.2L12 20l-2.2-7.3L3 10.5l6.8-2.2z"/>',
    "workflow": '<circle cx="5" cy="6" r="2.5"/><circle cx="19" cy="6" r="2.5"/><circle cx="12" cy="19" r="2.5"/><path d="M7.5 6h9M6.5 8l4 9M17.5 8l-4 9"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "card": '<rect x="2" y="5" width="20" height="14" rx="2.5"/><path d="M2 10h20M6 15h4"/>',
    "nfc": '<path d="M8 8a6 6 0 0 1 0 8"/><path d="M12 5a10 10 0 0 1 0 14"/><path d="M16 2.5a14 14 0 0 1 0 19"/>',
    "loop": '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "chart": '<path d="M4 20V11M10 20V4M16 20v-7M22 20H2"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "tag": '<path d="M3 12V3h9l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.4"/>',
    "wallet": '<path d="M3 7a2 2 0 0 1 2-2h13v4"/><rect x="3" y="7" width="18" height="13" rx="2.5"/><circle cx="16.5" cy="13.5" r="1.3"/>',
    "alert": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
}


def glyph(x, y, name, size=26, color="#FFFFFF", sw=1.8):
    s = size / 24
    return (f'<g transform="translate({x} {y}) scale({s})" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[name]}</g>')


def tile(x, y, name, size=54, color=CYAN, fill="#0D2557"):
    return (rect(x, y, size, size, 14, fill=fill, stroke="#5C8DFF", sw=1.1) +
            glyph(x + size * 0.23, y + size * 0.23, name, size * 0.54, color))


# ------------------------------------------------------------------ brand marks (own drawings, generic)
def logo(x, y, kind, size=44, label=None, label_color="#DCE8FF", label_size=14):
    s = size
    g = []
    if kind == "shortcuts":
        g.append(rect(x, y, s, s, s * .24, fill="url(#gShortcuts)"))
        g.append(f'<g transform="translate({x + s*.22} {y + s*.2})" fill="none" stroke="#fff" stroke-width="{s*.075}" '
                 f'stroke-linejoin="round"><path d="M{s*.0} {s*.18} L{s*.28} {s*.0} L{s*.56} {s*.18} L{s*.28} {s*.36}z"/>'
                 f'<path d="M{s*.0} {s*.36} L{s*.28} {s*.54} L{s*.56} {s*.36}" /></g>')
    elif kind == "github":
        g.append(rect(x, y, s, s, s * .24, fill="#161B26", stroke="#6B7A99", sw=1.2))
        g.append(glyph(x + s * .2, y + s * .2, "workflow", s * .6, "#FFFFFF", 2))
    elif kind == "supabase":
        g.append(rect(x, y, s, s, s * .24, fill="#0E1F1A", stroke="#2E8F6A", sw=1.2))
        g.append(f'<path d="M{x+s*.56} {y+s*.12} L{x+s*.22} {y+s*.58} H{x+s*.48} L{x+s*.42} {y+s*.88} L{x+s*.78} {y+s*.42} '
                 f'H{x+s*.52}z" fill="url(#gSupabase)"/>')
    elif kind == "postgres":
        g.append(rect(x, y, s, s, s * .24, fill="#2E5E8E", stroke="#7FB0E0", sw=1.2))
        g.append(glyph(x + s * .2, y + s * .2, "database", s * .6, "#FFFFFF", 1.9))
    elif kind == "python":
        g.append(rect(x, y, s, s, s * .24, fill="#10244E", stroke="#4A78C9", sw=1.2))
        g.append(rect(x + s * .2, y + s * .18, s * .36, s * .36, s * .1, fill="#3C7CC4"))
        g.append(rect(x + s * .44, y + s * .46, s * .36, s * .36, s * .1, fill="#FFD43B"))
    elif kind == "telegram":
        g.append(f'<circle cx="{x+s/2}" cy="{y+s/2}" r="{s/2}" fill="#2AA7E8"/>')
        g.append(glyph(x + s * .24, y + s * .22, "send", s * .52, "#FFFFFF", 2))
    elif kind == "claude":
        g.append(rect(x, y, s, s, s * .24, fill="#D97757"))
        c = f'translate({x+s/2} {y+s/2})'
        rays = "".join(f'<rect x="{-s*.035}" y="{-s*.34}" width="{s*.07}" height="{s*.3}" rx="{s*.035}" '
                       f'transform="rotate({a})"/>' for a in range(0, 360, 45))
        g.append(f'<g transform="{c}" fill="#fff">{rays}</g>')
    elif kind == "vision":
        g.append(rect(x, y, s, s, s * .24, fill="#2B1B66", stroke="#8B7BFF", sw=1.2))
        g.append(glyph(x + s * .2, y + s * .2, "eye", s * .6, "#C9BFFF", 1.9))
    elif kind == "ios":
        g.append(rect(x, y, s, s, s * .24, fill="#0B0F1A", stroke="#8A94A8", sw=1.2))
        g.append(glyph(x + s * .2, y + s * .2, "phone", s * .6, "#FFFFFF", 1.9))
    if label:
        g.append(T(x + s / 2, y + s + 19, label, label_size, 500, label_color, "middle"))
    return "".join(g)


# ------------------------------------------------------------------ shared chrome
def defs():
    return f"""
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#040A1C"/><stop offset="0.55" stop-color="#091A46"/><stop offset="1" stop-color="#050E2B"/>
  </linearGradient>
  <radialGradient id="glowA" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#22D3EE" stop-opacity="0.35"/><stop offset="1" stop-color="#22D3EE" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="glowB" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#8B5CF6" stop-opacity="0.38"/><stop offset="1" stop-color="#8B5CF6" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="title" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#22D3EE"/><stop offset="1" stop-color="#9B7BFF"/>
  </linearGradient>
  <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#22D3EE"/><stop offset="1" stop-color="#8B5CF6"/>
  </linearGradient>
  <linearGradient id="glassFill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF" stop-opacity="0.075"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0.025"/>
  </linearGradient>
  <linearGradient id="glassStrong" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#7FA8FF" stop-opacity="0.20"/><stop offset="1" stop-color="#7FA8FF" stop-opacity="0.07"/>
  </linearGradient>
  <linearGradient id="gShortcuts" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#FF5F8F"/><stop offset="0.55" stop-color="#C45BFF"/><stop offset="1" stop-color="#4C6BFF"/>
  </linearGradient>
  <linearGradient id="gSupabase" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#6BF0B4"/><stop offset="1" stop-color="#1F9D6B"/>
  </linearGradient>
  <linearGradient id="phoneBody" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#2A3A66"/><stop offset="1" stop-color="#0E1736"/>
  </linearGradient>
  <filter id="soft" x="-10%" y="-10%" width="120%" height="130%">
    <feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#000A2E" flood-opacity="0.45"/>
  </filter>
  <filter id="blur40"><feGaussianBlur stdDeviation="40"/></filter>
  <marker id="arrowHead" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M0 0L10 5L0 10z" fill="#8FB4FF"/>
  </marker>
  <marker id="arrowRose" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M0 0L10 5L0 10z" fill="{ROSE}"/>
  </marker>
</defs>"""


def background():
    return f"""
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<ellipse cx="780" cy="40" rx="520" ry="150" fill="url(#glowA)"/>
<ellipse cx="1400" cy="150" rx="380" ry="260" fill="url(#glowB)"/>
<ellipse cx="120" cy="980" rx="420" ry="200" fill="url(#glowB)" opacity="0.55"/>
<path d="M-40 150 C 260 40, 560 -20, 860 70 S 1320 40, 1600 -10" stroke="#5CC8FF" stroke-opacity="0.35" stroke-width="1.5" fill="none"/>
<path d="M-40 190 C 300 90, 600 20, 900 120 S 1340 100, 1600 40" stroke="#9B7BFF" stroke-opacity="0.30" stroke-width="1.3" fill="none"/>
"""


def header(sub="AUTOMATION  ·  DATA  ·  AI AGENTS"):
    mark = (rect(62, 44, 56, 56, 16, fill="url(#accent)") +
            glyph(74, 56, "wallet", 32, "#FFFFFF", 2))
    return (mark + T(134, 70, "Personal Finance System", 25, 700) + T(134, 92, sub, 12.5, 500, "#8FB4FF", ls=2.4) +
            T(W - 66, 76, "Built with Supabase, GitHub Actions & Claude", 22, 400, "#CFE0FF", "end", family=SCRIPT, rot=-3) +
            f'<path d="M{W-440} 108 Q {W-250} 100 {W-66} 90" stroke="url(#accent)" stroke-width="2.2" fill="none" stroke-linecap="round"/>')


def footer_takeaway(n, text, icon="check"):
    y = 940
    dots = "".join(f'<circle cx="{W-110+i*22}" cy="{y+37}" r="{6 if i+1==n else 4.5}" '
                   f'fill="{"#22D3EE" if i+1==n else "#35508F"}"/>' for i in range(4))
    return (rect(62, y, W - 124, 74, 18, fill="url(#glassStrong)", stroke="#6EA8FF", sw=1.1) +
            tile(78, y + 10, icon, 54, CYAN) + T(150, y + 44, text, 20, 500, "#EAF1FF") + dots)


def svg(body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{escape(title)}">{defs()}{background()}{body}</svg>')


def heading(kicker, line1, line2, sub):
    return (T(62, 168, kicker, 15, 700, "#7FB5FF", ls=3) +
            T(62, 228, line1, 52, 700) +
            f'<text x="62" y="288" font-family="{SANS}" font-size="52" font-weight="700" fill="url(#title)">{escape(line2)}</text>' +
            T(62, 330, sub, 19, 400, "#C9D8F5"))


# ------------------------------------------------------------------ SLIDE 1: overview
def slide1():
    b = [header()]
    b.append(T(62, 215, "Zero-Friction", 62, 700))
    b.append(f'<text x="62" y="283" font-family="{SANS}" font-size="62" font-weight="700" fill="url(#title)">Personal Finance</text>')
    b.append(f'<text x="62" y="351" font-family="{SANS}" font-size="62" font-weight="700" fill="url(#title)">System</text>')
    b.append(lines(64, 400, ["One tap on an iPhone records an expense.",
                             "It is validated, stored, labeled and",
                             "audited by AI, with no manual bookkeeping."], 20, 28, fill="#DCE8FF"))
    feats = [("nfc", "Capture anywhere", "NFC / Wallet tap, manual hub, receipt photo"),
             ("spark", "Deterministic first, AI second", "Keyword labels; vision model reads receipts"),
             ("moon", "Self-auditing", "Nightly Claude routine fixes labels and learns"),
             ("shield", "Secure by design", "RLS on every table, no secrets in code")]
    for i, (ic, t, d) in enumerate(feats):
        y = 492 + i * 62
        b.append(tile(62, y, ic, 56, CYAN))
        b.append(T(132, y + 25, t, 20, 600))
        b.append(T(132, y + 47, d, 15.5, 400, "#A9BDE8"))
    b.append(T(64, 786, "From a tap to a trusted ledger.", 28, 400, "#CFE0FF", family=SCRIPT, rot=-2))
    b.append(f'<path d="M64 800 Q 260 792 470 795" stroke="url(#accent)" stroke-width="2.4" fill="none" stroke-linecap="round"/>')

    # right: glass frame with phone + proof tiles
    fx, fy, fw, fh = 600, 150, 880, 640
    b.append(rect(fx, fy, fw, fh, 22, fill="url(#glassFill)", stroke="#4D86FF", sw=1.4))
    # phone
    px, py, pw, ph = 640, 190, 290, 560
    b.append(rect(px, py, pw, ph, 38, fill="url(#phoneBody)", stroke="#7FA8FF", sw=2))
    b.append(rect(px + 12, py + 12, pw - 24, ph - 24, 28, fill="#0A1230"))
    b.append(rect(px + pw / 2 - 42, py + 20, 84, 20, 10, fill="#02050F"))
    b.append(T(px + 30, py + 78, "Shortcuts", 14, 700, "#8FB4FF", ls=2))
    b.append(T(px + 30, py + 110, "What are you logging?", 20, 700))
    items = [("Rent", True), ("Gym membership", False), ("Subscription", False),
             ("Savings deposit", False), ("Credit card payment", False)]
    for i, (name, hot) in enumerate(items):
        yy = py + 136 + i * 58
        b.append(rect(px + 24, yy, pw - 48, 46, 13, fill="#1B2E66" if not hot else "url(#accent)", stroke="#4D6BD0", sw=1))
        b.append(T(px + 44, yy + 30, name, 17, 600, "#FFFFFF"))
        b.append(glyph(px + pw - 62, yy + 11, "check" if hot else "list", 24, "#FFFFFF" if hot else "#7F97D6", 2))
    b.append(rect(px + 24, py + 438, pw - 48, 78, 14, fill="#12306F", stroke="#3F72E8"))
    b.append(logo(px + 34, py + 452, "telegram", 34))
    b.append(T(px + 78, py + 466, "Ingestion 'rent' recorded", 15, 700))
    b.append(T(px + 78, py + 488, "Rent payment  -500.00 €", 14.5, 400, "#BFD2FF"))
    # arrow + proof tiles
    b.append(path_arrow("M936 470 C 975 470, 975 470, 1010 470", "#8FB4FF", 2.4))
    tiles = [("600+", "real transactions", "in production use", "database"),
             ("36", "automated tests", "CI green on every push", "check"),
             ("3 + 5", "Shortcuts + workflows", "capture · photo · fixed", "workflow"),
             ("8", "tables, 4 views", "row-level security on all", "shield")]
    for i, (big, l1, l2, ic) in enumerate(tiles):
        cx = 1020 + (i % 2) * 220
        cy = 200 + (i // 2) * 270 + 20
        b.append(rect(cx, cy, 200, 240, 18, fill="url(#glassStrong)", stroke="#6EA8FF", sw=1.1))
        b.append(glyph(cx + 18, cy + 18, ic, 30, CYAN, 1.9))
        b.append(f'<text x="{cx+18}" y="{cy+112}" font-family="{SANS}" font-size="52" font-weight="700" fill="url(#title)">{escape(big)}</text>')
        b.append(T(cx + 18, cy + 150, l1, 17, 600))
        b.append(T(cx + 18, cy + 174, l2, 14.5, 400, "#A9BDE8"))
    # bottom band
    b.append(rect(0, 808, W, 216, 0, fill="#050C26", opacity=0.55))
    b.append(f'<path d="M0 808 H{W}" stroke="#2C4C97" stroke-width="1"/>')
    b.append(T(62, 850, "Technologies & platform", 20, 600))
    techs = [("shortcuts", "iOS Shortcuts"), ("github", "GitHub Actions"), ("supabase", "Supabase"), ("postgres", "PostgreSQL"),
             ("python", "Python"), ("telegram", "Telegram"), ("claude", "Claude"), ("vision", "Vision AI")]
    for i, (k, lab) in enumerate(techs):
        b.append(logo(62 + i * 112, 868, k, 46, lab, label_size=13))
    b.append(f'<path d="M980 840 V990" stroke="#2C4C97" stroke-width="1"/>')
    b.append(T(1008, 850, "What this demonstrates", 20, 600))
    proofs = [("workflow", "End-to-end architecture"), ("lock", "Security & data modeling"),
              ("spark", "AI in production"), ("loop", "Tested, repeatable delivery")]
    for i, (ic, t) in enumerate(proofs):
        xx = 1008 + (i % 2) * 250
        yy = 874 + (i // 2) * 54
        b.append(glyph(xx, yy, ic, 26, CYAN, 1.9))
        b.append(T(xx + 36, yy + 20, t, 16, 500, "#EAF1FF"))
    return svg("".join(b), "Zero-Friction Personal Finance System: overview")


# ------------------------------------------------------------------ SLIDE 2: architecture & flow
def stage(x, y, w, h, n, icon, title, sub, rows, tone="lav"):
    o = [light(x, y, w, h, 14, tone)]
    o.append(f'<circle cx="{x+26}" cy="{y+28}" r="15" fill="#14206B"/>' + T(x + 26, y + 34, str(n), 16, 700, "#FFFFFF", "middle"))
    o.append(glyph(x + w - 46, y + 12, icon, 30, "#3750C8", 1.9))
    o.append(T(x + 50, y + 33, title, 19, 700, NAVY_TXT))
    o.append(T(x + 16, y + 62, sub, 14.5, 500, "#4A5BB0"))
    o.append(lines(x + 16, y + 92, rows, 14.5, 21, fill="#1B2A78"))
    return "".join(o)


def slide2():
    b = [header()]
    b.append(heading("ARCHITECTURE & FLOW", "From tap to ledger,", "and what happens when it fails",
                     "Five stages, one safety net: nothing is lost, everything is auditable."))
    sx, sy, sw, sh, gap = 62, 372, 260, 228, 28
    stages = [
        (1, "phone", "Capture", "iOS Shortcuts · 3 flows",
         ["NFC / Wallet transaction", "Manual hub (income, expense)", "Fixed expenses in one tap", "Receipt photo → private bucket"], "lav"),
        (2, "send", "Dispatch", "GitHub repository_dispatch",
         ["One HTTPS call per record", "Typed event: dynamic,", "photo or standardized", "Token scoped to one repo"], "lav"),
        (3, "workflow", "Process", "GitHub Actions · Python",
         ["Resolve account, category,", "label and date rules", "Vision model for receipts", "Deterministic matching first"], "cyan"),
        (4, "database", "Store", "Supabase · PostgreSQL",
         ["Versioned categories (SCD2)", "Trigger sets payment medium", "RLS on every table", "Private receipts bucket"], "mint"),
        (5, "send", "Notify", "Telegram bot",
         ["Success: rows and ids", "Failure: pending record", "created automatically", "Reason is always sent"], "lav"),
    ]
    for i, (n, ic, t, sub, rows, tone) in enumerate(stages):
        x = sx + i * (sw + gap)
        b.append(stage(x, sy, sw, sh, n, ic, t, sub, rows, tone))
        if i < 4:
            b.append(arrow(x + sw + 3, sy + 114, x + sw + gap - 3, sy + 114, "#8FB4FF", 2.6))
    # failure lane
    ly = 650
    b.append(rect(62, ly, W - 124, 250, 20, fill="url(#glassFill)", stroke="#FB7185", sw=1.3, extra='stroke-dasharray="7 6"'))
    b.append(T(86, ly + 36, "SAFETY NET  ·  NIGHTLY AI AUDIT", 14, 700, ROSE, ls=2.6))
    lane = [("alert", "Any failure", "bad data, no keyword match, API down", ROSE),
            ("list", "Pending record", "registros_pendientes keeps the payload", AMBER),
            ("moon", "Claude routine", "reads via MCP, one INSERT per pending", CYAN),
            ("tag", "Audit + learn", "fixes labels, adds keywords to glossary", MINT),
            ("trash", "Daily purge", "GitHub job removes processed pendings", "#9FB4E8")]
    cw, cg = 252, 29
    for i, (ic, t, d, col) in enumerate(lane):
        x = 86 + i * (cw + cg)
        b.append(rect(x, ly + 58, cw, 150, 16, fill="url(#glassStrong)", stroke=col, sw=1.2))
        b.append(glyph(x + 16, ly + 74, ic, 32, col, 1.9))
        b.append(T(x + 60, ly + 98, t, 18.5, 700))
        b.append(lines(x + 16, ly + 140, _wrap(d, 29), 15, 21, fill="#BFD2FF"))
        if i < 4:
            b.append(arrow(x + cw + 3, ly + 133, x + cw + cg - 3, ly + 133, col if col != "#9FB4E8" else "#8FB4FF", 2.4))
    # connector from stage 3/4 to lane
    b.append(path_arrow(f"M{sx + 2*(sw+gap) + sw/2} {sy + sh + 4} V {ly - 2}", ROSE, 2.4, "6 5"))
    b.append(T(sx + 2 * (sw + gap) + sw / 2 + 14, sy + sh + 30, "on failure", 14, 600, ROSE))
    b.append(footer_takeaway(2, "Idempotent by design: the routine checks for duplicates before inserting and never deletes data.", "shield"))
    return svg("".join(b), "Architecture and flow")


def _wrap(s, n):
    words, out, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


# ------------------------------------------------------------------ SLIDE 3: shortcuts & ingestion logic
def slide3():
    b = [header()]
    b.append(heading("INSIDE THE SHORTCUTS", "Three Shortcuts,", "one decision tree per record",
                     "Every branch ends in the same typed payload; the workflow decides how to record it."))
    cards = [
        ("wallet", "Compras", "Wallet / NFC trigger", ["Pick account", "Pick categories", "Receipt? yes → photo upload", "Receipt? no → amount per category"]),
        ("edit", "Manufinanza", "Manual hub", ["Income → account, amount, note", "Expense → account, categories", "Photo or manual lines", "System date, one payload"]),
        ("clock", "Gasto_fijo", "Fixed expenses", ["Up to 7 one-tap expenses", "Fixed amount + fixed account", "Savings deposit / withdrawal", "Credit card payment (2 rows)"]),
    ]
    cx0, cy0, cw, ch, cg = 62, 360, 452, 214, 28
    centers = []
    for i, (ic, t, sub, rows) in enumerate(cards):
        x = cx0 + i * (cw + cg)
        centers.append(x + cw / 2)
        b.append(light(x, cy0, cw, ch, 14, "lav"))
        b.append(glyph(x + 16, cy0 + 14, ic, 30, "#3750C8", 1.9))
        b.append(T(x + 58, cy0 + 40, t, 22, 700, NAVY_TXT))
        b.append(T(x + cw - 16, cy0 + 40, sub, 14.5, 600, "#4A5BB0", "end"))
        for j, r in enumerate(rows):
            b.append(f'<circle cx="{x+24}" cy="{cy0+90+j*32-5}" r="3.5" fill="#3750C8"/>')
            b.append(T(x + 38, cy0 + 90 + j * 32, r, 17, 500, "#1B2A78"))
    # one bar: every Shortcut ends in the same dispatch
    by = cy0 + ch + 14
    for cx in centers:
        b.append(arrow(cx, cy0 + ch + 3, cx, by - 2, "#8FB4FF", 2.2))
    b.append(rect(62, by, W - 124, 30, 15, fill="#0F2A66", stroke="#6EA8FF", sw=1))
    b.append(T(W / 2, by + 20.5, "GitHub repository_dispatch  ·  one typed event per record", 15, 600, "#DCE8FF", "middle"))
    # decision trees (3 columns, one per event type)
    ty = by + 52
    colx = [86, 556, 1026]
    colw = 424
    cols = [
        ("gasto_dinamico", "DYNAMIC", CYAN, ["Category-bounded keyword match", "Hit → insert rows, signed by type", "Miss → pending for nightly AI"]),
        ("gasto_foto", "PHOTO", PURPLE, ["Label menu for chosen categories", "Glossary overrides the model", "Sum ≠ TOTAL → one re-read, else pending"]),
        ("ingesta_estandarizada", "STANDARDIZED", MINT, ["Template valid on that date", "Fixed rows, or linked rows", "Card payment: card −, account +"]),
    ]
    b.append(rect(62, ty - 8, W - 124, 276, 20, fill="url(#glassFill)", stroke="#4D86FF", sw=1.2))
    for i, (ev, t, col, rows) in enumerate(cols):
        x = colx[i]
        b.append(T(x, ty + 24, t + " INGESTION", 14, 700, col, ls=2.4))
        w = int(len(ev) * 7.6 + 24)
        b.append(chip(x + colw - w, ty + 5, ev, w, "#0F2A66", col, "#DCE8FF", 13.5))
        for j, r in enumerate(rows):
            yy = ty + 44 + j * 66
            b.append(rect(x, yy, colw, 52, 12, fill="url(#glassStrong)", stroke=col, sw=1.1))
            b.append(f'<circle cx="{x+26}" cy="{yy+26}" r="13" fill="{col}"/>')
            b.append(T(x + 26, yy + 31, str(j + 1), 14, 700, "#06122E", "middle"))
            b.append(T(x + 50, yy + 32, r, 17, 500, "#EAF1FF"))
            if j < 2:
                b.append(arrow(x + 26, yy + 52, x + 26, yy + 66, col, 2))
    b.append(footer_takeaway(3, "A closed vocabulary of categories keeps AI from ever touching the budget: it only picks numbers from a menu.", "tag"))
    return svg("".join(b), "Shortcuts and ingestion logic")


# ------------------------------------------------------------------ SLIDE 4: data model + control + routine
def table_box(x, y, w, title, gloss, cols, accent=CYAN):
    h = 52 + len(cols) * 19 + 10
    o = [rect(x, y, w, h, 12, fill="url(#glassStrong)", stroke=accent, sw=1.2)]
    o.append(T(x + 12, y + 22, title, 15.5, 700))
    o.append(T(x + 12, y + 40, gloss, 12.5, 500, accent))
    for i, c in enumerate(cols):
        o.append(T(x + 12, y + 62 + i * 19, c, 13.5, 400, "#BFD2FF"))
    return "".join(o), h


def slide4():
    b = [header()]
    b.append(heading("DATA MODEL & FINANCIAL CONTROL", "A ledger you can trust,", "with budgets that follow your life",
                     "Eight tables, four views, seven budget periods; every figure is derived, never typed."))
    ey, eh = 346, 360
    b.append(rect(54, ey, 836, eh, 18, fill="url(#glassFill)", stroke="#4D86FF", sw=1.2))
    b.append(T(72, ey + 24, "ENTITY MODEL", 13, 700, "#7FB5FF", ls=2.6))
    specs = {
        "cuentas": ("accounts", ["name · nature", "payment medium (debit / credit)"], 70, 376, 250, CYAN),
        "categorias": ("categories · versioned (SCD2)", ["code · type · period · budget", "valid from / to"], 70, 486, 250, PURPLE),
        "etiquetas": ("labels", ["name · criterion", "keywords · allowed categories"], 70, 596, 250, MINT),
        "seguimiento_efectivo": ("LEDGER", ["amount · type · date", "account → category → label", "payment medium set by trigger"], 380, 436, 250, AMBER),
        "auditoria_cambios": ("audit trail", ["label before/after · reason"], 380, 596, 250, MINT),
        "tarjeta_credito": ("credit cards", ["limit per card"], 660, 376, 210, CYAN),
        "rutina_nocturna_log": ("run log + watermark", ["rows audited · fixes"], 660, 486, 210, MINT),
        "registros_pendientes": ("pendings", ["payload · error · status"], 660, 596, 210, ROSE),
    }
    pos = {}
    for name, (gl, cols, x, y, w, col) in specs.items():
        s_, h = table_box(x, y, w, name, gl, cols, col)
        b.append(s_)
        pos[name] = (x, y, w, h)
    L = pos["seguimiento_efectivo"]
    for k, nm in enumerate(("cuentas", "categorias", "etiquetas")):
        x, y, w, h = pos[nm]
        ty_ = L[1] + 36 + k * 26
        b.append(path_arrow(f"M{x+w} {y+h/2} C {x+w+30} {y+h/2}, {L[0]-30} {ty_}, {L[0]-2} {ty_}", "#8FB4FF", 2))
    cx_, cy_, cw_, ch_ = pos["cuentas"]
    tx, ty0, tw, th = pos["tarjeta_credito"]
    b.append(path_arrow(f"M{tx} {ty0+30} H {cx_+cw_+4}", "#8FB4FF", 2, "5 4"))
    rx, ry_, rw, rh = pos["registros_pendientes"]
    b.append(path_arrow(f"M{L[0]+L[2]} {L[1]+L[3]-30} H {L[0]+L[2]+14} V {ry_+30} H {rx-2}", ROSE, 2, "6 5"))
    ax, ay, aw, ah = pos["auditoria_cambios"]
    b.append(path_arrow(f"M{L[0]+L[2]/2} {L[1]+L[3]+2} V {ay-2}", "#8FB4FF", 2, "5 4"))
    # views
    vx = 900
    b.append(rect(vx, ey, 574, eh, 18, fill="url(#glassFill)", stroke="#4D86FF", sw=1.2))
    b.append(T(vx + 18, ey + 24, "FINANCIAL CONTROL (VIEWS)", 13, 700, "#7FB5FF", ls=2.6))
    views = [("wallet", "Account balances", "per account, always derived"),
             ("card", "Credit per card", "debt and available limit, any number of cards"),
             ("chart", "Monthly budget", "period budget ÷ months vs this month's spending"),
             ("layers", "Annual budget", "yearly categories vs this year's spending")]
    for i, (ic, t, d) in enumerate(views):
        yy = ey + 40 + i * 62
        b.append(rect(vx + 16, yy, 542, 54, 12, fill="url(#glassStrong)", stroke="#6EA8FF", sw=1))
        b.append(glyph(vx + 30, yy + 13, ic, 28, CYAN, 1.9))
        b.append(T(vx + 74, yy + 25, t, 17, 700))
        b.append(T(vx + 74, yy + 44, d, 14, 400, "#A9BDE8"))
    b.append(T(vx + 18, ey + 306, "BUDGET PERIODS", 12.5, 700, "#7FB5FF", ls=2.4))
    px = vx + 16
    for lab in ["monthly", "2 months", "quarterly", "4 months", "semiannual", "yearly", "one-off"]:
        w = int(len(lab) * 6.7 + 16)
        b.append(chip(px, ey + 318, lab, w, "#13306F", "#6EA8FF", "#DCE8FF", 12.5))
        px += w + 5
    # nightly routine
    ry = 718
    b.append(rect(62, ry, W - 124, 206, 20, fill="url(#glassFill)", stroke="#8B5CF6", sw=1.3))
    b.append(logo(80, ry + 16, "claude", 40))
    b.append(T(132, ry + 36, "Nightly Claude Code routine", 20, 700))
    b.append(T(132, ry + 58, "Runs unattended through the Supabase MCP connector; every write is an INSERT or an UPDATE with a WHERE.", 15, 400, "#BFD2FF"))
    phases = [("clock", "Context", "watermark and cap"), ("list", "Pendings", "one INSERT each"),
              ("search", "Validate", "label vs criterion"), ("tag", "Glossary", "new keywords"),
              ("send", "Report", "log + Telegram")]
    pw, pg = 254, 24
    for i, (ic, t, d) in enumerate(phases):
        x = 82 + i * (pw + pg)
        b.append(rect(x, ry + 84, pw, 92, 14, fill="url(#glassStrong)", stroke="#8B7BFF", sw=1.1))
        b.append(glyph(x + 14, ry + 100, ic, 28, "#C9BFFF", 1.9))
        b.append(T(x + 52, ry + 122, f"{i+1}. {t}", 17, 700))
        b.append(T(x + 52, ry + 146, d, 14, 400, "#A9BDE8"))
        if i < 4:
            b.append(arrow(x + pw + 1, ry + 130, x + pw + pg - 1, ry + 130, "#8B7BFF", 2.2))
    b.append(footer_takeaway(4, "Data modeling, security, automation and AI operations in one delivered, tested system.", "spark"))
    return svg("".join(b), "Data model and financial control")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "docs", "portfolio")
    os.makedirs(out, exist_ok=True)
    for name, fn in (("slide-1-overview", slide1), ("slide-2-architecture", slide2),
                     ("slide-3-shortcuts", slide3), ("slide-4-data-and-control", slide4)):
        p = os.path.join(out, name + ".svg")
        open(p, "w", encoding="utf-8").write(fn())
        print(p)


if __name__ == "__main__":
    main()
