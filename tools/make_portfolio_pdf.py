# -*- coding: utf-8 -*-
"""Builds the technical portfolio document of the project (PDF, A4) in the same
layout, palette and section structure as the author's other portfolio documents.

    pip install reportlab
    python tools/make_portfolio_pdf.py [output.pdf]
"""
import os
import sys

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
                                Preformatted, Spacer, Table, TableStyle)

DOC_ID = "PF-2609-PY-003"
VERSION = "v1"
TITLE_SHORT = "Personal Finance System"
AUTHOR = "Diego Calle"

TEAL = HexColor("#0096C0")
TEAL_D = HexColor("#007BA0")
CYAN = HexColor("#00B5D8")
NAVY = HexColor("#0B2540")
PALE = HexColor("#E8F6FB")
LINE = HexColor("#D5E3EA")
TEXT = HexColor("#444444")
HEAD = HexColor("#333333")
AMBER_BG = HexColor("#FFF8E1")
AMBER = HexColor("#F5B800")
CODE = HexColor("#1F2D3D")

PAGE_W, PAGE_H = A4
LM = RM = 20 * mm
CW = PAGE_W - LM - RM  # content width

body = ParagraphStyle("body", fontName="Helvetica", fontSize=8.8, leading=12.6, textColor=TEXT, spaceAfter=5, alignment=TA_LEFT)
cell = ParagraphStyle("cell", parent=body, fontSize=8.4, leading=11.2, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")
cellh = ParagraphStyle("cellh", parent=cell, fontName="Helvetica-Bold", textColor=white)
h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=TEAL_D, spaceAfter=10)
h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=TEAL_D, spaceBefore=11, spaceAfter=6)
h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=HEAD, spaceBefore=8, spaceAfter=4)
h4 = ParagraphStyle("h4", fontName="Helvetica-Bold", fontSize=9.6, leading=12.5, textColor=HEAD, spaceBefore=6, spaceAfter=3)
cap = ParagraphStyle("cap", fontName="Helvetica-Oblique", fontSize=8.2, leading=11, textColor=TEXT, spaceBefore=3, spaceAfter=8)
meta = ParagraphStyle("meta", fontName="Helvetica-Oblique", fontSize=8.8, leading=12.4, textColor=TEXT)
snip = ParagraphStyle("snip", fontName="Helvetica-Oblique", fontSize=8.4, leading=11, textColor=TEXT, spaceBefore=4, spaceAfter=3)


def P(t, s=body):
    return Paragraph(t, s)


def table(rows, widths, header=True, first_bold=True, pad=4):
    data = []
    for i, r in enumerate(rows):
        out = []
        for j, c in enumerate(r):
            if header and i == 0:
                out.append(Paragraph(c, cellh))
            elif j == 0 and first_bold:
                out.append(Paragraph(c, cellb))
            else:
                out.append(Paragraph(c, cell))
        data.append(out)
    t = Table(data, colWidths=[w * CW for w in widths], repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
          ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad + 1),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("LINEBEFORE", (0, 0), (0, -1), 0.4, LINE),
          ("LINEAFTER", (-1, 0), (-1, -1), 0.4, LINE)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), TEAL))
    for i in range(1 if header else 0, len(rows)):
        if (i - (1 if header else 0)) % 2 == 1:
            st.append(("BACKGROUND", (0, i), (-1, i), PALE))
    t.setStyle(TableStyle(st))
    return t


def chips(items, per_row=7):
    rows = [items[i:i + per_row] for i in range(0, len(items), per_row)]
    rows = [r + [""] * (per_row - len(r)) for r in rows]
    cs = ParagraphStyle("chip", parent=cellb, textColor=TEAL_D, alignment=1, fontSize=8.4, leading=10.5)
    data = [[Paragraph(c, cs) if c else "" for c in r] for r in rows]
    t = Table(data, colWidths=[CW / per_row] * per_row, rowHeights=[32] * len(rows))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.6, TEAL),
                           ("INNERGRID", (0, 0), (-1, -1), 0.5, TEAL), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


def code_block(text):
    t = Table([[Preformatted(text, ParagraphStyle("code", fontName="Courier", fontSize=7.2, leading=9.2, textColor=CODE))]],
              colWidths=[CW])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#9ED4E8")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def stat_cards(items):
    n = len(items)
    big = ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=TEAL_D, alignment=1)
    lab = ParagraphStyle("lab", fontName="Helvetica", fontSize=8.4, leading=11, textColor=TEXT, alignment=1)
    data = [[Paragraph(v, big) for v, _ in items], [Paragraph(l, lab) for _, l in items]]
    t = Table(data, colWidths=[CW / n] * n)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.6, TEAL),
                           ("INNERGRID", (0, 0), (-1, -1), 0.5, white), ("TOPPADDING", (0, 0), (-1, 0), 9),
                           ("BOTTOMPADDING", (0, 1), (-1, 1), 9)]))
    return t


# ------------------------------------------------------------------ figures
def _box(d, x, y, w, h, title, sub="", dark=False, size=8.6):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=NAVY if dark else PALE, strokeColor=NAVY if dark else TEAL, strokeWidth=0.9))
    col = white if dark else HEAD
    subcol = HexColor("#CFE0EA") if dark else TEXT
    lines = sub.split("\n") if sub else []
    ty = y + h / 2 + (len(lines) * 4.2) + 1.5
    d.add(String(x + w / 2, ty, title, fontName="Helvetica-Bold", fontSize=size, fillColor=col, textAnchor="middle"))
    for i, l in enumerate(lines):
        d.add(String(x + w / 2, ty - 11.5 - i * 9.6, l, fontName="Helvetica", fontSize=7.2, fillColor=subcol, textAnchor="middle"))


def _arrow(d, x1, y1, x2, y2, color=TEAL):
    import math
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1))
    a = math.atan2(y2 - y1, x2 - x1)
    s = 4.6
    p = [x2, y2, x2 - s * math.cos(a - 0.45), y2 - s * math.sin(a - 0.45), x2 - s * math.cos(a + 0.45), y2 - s * math.sin(a + 0.45)]
    d.add(Polygon(p, fillColor=color, strokeColor=color, strokeWidth=0.4))


def _label(d, x, y, t, color=TEAL_D, size=7.4, anchor="middle", bold=True, italic=False):
    f = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else "Helvetica")
    d.add(String(x, y, t, fontName=f, fontSize=size, fillColor=color, textAnchor=anchor))


def fig_loop():
    d = Drawing(CW, 108)
    bw, gap = 84, (CW - 5 * 84) / 4
    labels = [("1  CAPTURE", "iOS Shortcuts\n3 flows"), ("2  PROCESS", "GitHub Actions\nPython"),
              ("3  STORE", "Supabase\nPostgreSQL"), ("4  NOTIFY", "Telegram\nresult or reason"),
              ("5  AUDIT", "Nightly Claude\nroutine")]
    for i, (t, s) in enumerate(labels):
        x = i * (bw + gap)
        _box(d, x, 46, bw, 54, t, s, dark=(i == 4))
        if i < 4:
            _arrow(d, x + bw + 1, 73, x + bw + gap - 1, 73)
    x5, x1 = 4 * (bw + gap) + bw / 2, bw / 2
    d.add(Line(x5, 46, x5, 22, strokeColor=TEAL, strokeWidth=1))
    d.add(Line(x5, 22, x1, 22, strokeColor=TEAL, strokeWidth=1))
    _arrow(d, x1, 22, x1, 45)
    _label(d, CW / 2, 9, "failures and unmatched records become pendings; the audit resolves them and teaches the next record", TEXT, 7.4, bold=False, italic=True)
    return d


def fig_tree():
    d = Drawing(CW, 262)
    qx, qw, qh = 0, 258, 46
    rx, rw = 322, CW - 322
    rows = [
        ("1. Is it a recurring item with a fixed amount", "and a fixed paying account?", "Fixed template", "tipo_ingesta + date only", True),
        ("2. Is it a savings move or a credit card", "payment (two accounts involved)?", "Linked rows", "one atomic INSERT", True),
        ("3. Is there a receipt photo?", "", "Vision menu + glossary", "amounts checked vs TOTAL", False),
        ("4. Otherwise: category chosen in the Shortcut", "", "Keyword match", "hit: insert / miss: pending", True),
    ]
    top = 262
    for i, (l1, l2, rt, rs, dark) in enumerate(rows):
        y = top - 46 - i * 72
        d.add(Rect(qx, y, qw, qh, rx=5, ry=5, fillColor=white, strokeColor=TEAL, strokeWidth=0.9))
        d.add(String(qx + 9, y + 28, l1, fontName="Helvetica-Bold", fontSize=8, fillColor=HEAD))
        if l2:
            d.add(String(qx + 9, y + 15, l2, fontName="Helvetica", fontSize=8, fillColor=TEXT))
        if i < 3:
            _arrow(d, qx + qw / 2, y - 1, qx + qw / 2, y - 25)
            _label(d, qx + qw / 2 + 14, y - 15, "NO", TEAL_D, 7.2, "start")
        if i < 3 or True:
            _arrow(d, qx + qw + 1, y + qh / 2, rx - 1, y + qh / 2)
            _label(d, (qx + qw + rx) / 2, y + qh / 2 + 6, "YES", TEAL_D, 7.2)
        _box(d, rx, y + 2, rw, qh - 4, rt, rs, dark=dark)
    return d


def fig_flow():
    d = Drawing(CW, 190)
    # top row
    _box(d, 0, 118, 108, 56, "01  Capture", "3 Shortcuts\nNFC / manual / photo")
    _box(d, 134, 118, 108, 56, "02  Dispatch", "repository_dispatch\n1 call per record")
    _box(d, 268, 118, 108, 56, "03  Process", "3 ingestion scripts\nGitHub Actions")
    _box(d, 402, 118, CW - 402, 56, "04  Store", "Supabase\nPostgreSQL")
    for x in (108, 242, 376):
        _arrow(d, x + 1, 146, x + 25, 146)
    # bottom
    _box(d, 134, 6, 242, 56, "Nightly Claude routine (MCP)", "resolves pendings, audits labels,\nadds keywords, writes the run log", dark=True)
    _box(d, 402, 6, CW - 402, 56, "Daily purge", "removes processed\npendings", )
    _arrow(d, 376 + 25, 34, 402 - 1, 34)
    _arrow(d, 322, 117, 322, 64, ROSE_D)
    _label(d, 330, 92, "failure / no match", ROSE_D, 7.2, "start")
    _arrow(d, 456, 117, 456, 64)
    _label(d, 464, 92, "rows", TEAL_D, 7.2, "start")
    _label(d, 0, 78, "Track 2: ingestion", TEAL_D, 8.2, "start")
    _label(d, 0, 66, "Track 3: audit and learning", TEAL_D, 8.2, "start")
    return d


ROSE_D = HexColor("#C0392B")


# ------------------------------------------------------------------ page decoration
def decorate(c, doc):
    c.saveState()
    c.setFont("Helvetica-Bold", 8.2)
    c.setFillColor(TEAL_D)
    c.drawString(LM, PAGE_H - 36, f"{TITLE_SHORT}  ·  {DOC_ID}  ·  {VERSION}")
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.line(LM, PAGE_H - 45.4, PAGE_W - RM, PAGE_H - 45.4)
    c.setFont("Helvetica", 8)
    c.setFillColor(TEXT)
    c.drawCentredString(PAGE_W / 2, 30, f"{AUTHOR} – Technical Portfolio – p. {doc.page}")
    c.restoreState()


# ------------------------------------------------------------------ content
def build(out):
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=62, bottomMargin=56,
                          title=f"{TITLE_SHORT}: Zero-Friction Expense Capture, Budget Control and AI Audit ({DOC_ID} {VERSION})",
                          author=AUTHOR)
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(LM, 56, CW, PAGE_H - 62 - 56, leftPadding=0, rightPadding=0,
                                                           topPadding=0, bottomPadding=0)], onPage=decorate)])
    s = []

    s.append(P("Personal Finance System:<br/>Zero-Friction Expense Capture, Budget Control<br/>and AI Audit", h1))
    t = Table([[Paragraph(f"<font color='white'><b>{DOC_ID}</b></font><br/><font color='white'>{VERSION}</font>",
                          ParagraphStyle("idc", parent=cell, textColor=white, leading=13)),
                Paragraph("Python / Supabase (PostgreSQL) / GitHub Actions / iOS Shortcuts / Claude · First documented "
                          "September 2026 · v1, October 2026<br/>Status: in operation (personal production) and released as an "
                          "open-source template. Track 1 (Capture), Track 2 (Ingestion), Track 3 (Audit).", meta)]],
              colWidths=[90, CW - 90])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), TEAL), ("BACKGROUND", (1, 0), (1, 0), PALE),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                           ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("LINEABOVE", (0, 0), (-1, -1), 0.4, LINE)]))
    s += [t, Spacer(1, 6)]

    s.append(P("2. Tool Stack", h2))
    s.append(chips(["Python 3.12", "PostgreSQL 17<br/>(Supabase)", "GitHub Actions", "iOS Shortcuts", "Supabase REST<br/>+ Storage",
                    "Supabase Vault<br/>+ pg_net", "Telegram<br/>Bot API", "Qwen3-VL<br/>(DashScope)", "Claude + MCP<br/>connector",
                    "requests 2.31+", "pytest 8+", "PyYAML 6+", "zoneinfo<br/>(stdlib)", "SQL views<br/>+ triggers"]))

    s.append(P("3. Project Objective", h2))
    s.append(P("Replace a manually maintained spreadsheet and a habit that people abandon after a few weeks with a closed-loop personal "
               "finance system with <b>zero-friction capture</b>: one tap on a phone records an expense, the system validates it, stores it "
               "in a relational ledger, labels it, reports the result, and <b>audits itself</b> every night. It covers the whole life of a "
               "record: <b>capture</b> it, <b>process</b> it, <b>store</b> it, <b>notify</b> the outcome and <b>audit</b> what could not be "
               "resolved automatically."))
    s.append(P("It was built as three linked tracks: iOS Shortcuts that capture (Track 1), GitHub Actions scripts that ingest into "
               "Supabase (Track 2) and a nightly Claude routine that audits and teaches the system (Track 3). A setup interview "
               "turns the same code base into a template that any user configures with their own accounts, categories and fixed expenses."))
    s.append(KeepTogether([fig_loop(), P("Figure 1. Closed loop: from the tap on the phone to the nightly audit that improves the next record.", cap)]))

    s.append(P("4. Problem It Solves", h2))
    s.append(P("Expense tracking fails for two reasons: capturing a record costs too much effort at the moment of payment, and unattended "
               "automation tends to be wrong in ways nobody notices. The result is a spreadsheet that is behind reality, labels that drift, "
               "budgets that cannot be trusted and a credit card balance nobody can reconcile. The challenge is to make capture almost free "
               "<i>and</i> keep the data trustworthy without a human reviewing every row."))
    s.append(table([
        ["Risk Category", "Concrete Manifestation"],
        ["Capture friction", "Opening an app, choosing fields and typing amounts at the till; people stop after a few weeks."],
        ["Silent failure", "A broken integration drops a record and nobody notices until the monthly reconciliation."],
        ["Inconsistent labeling", "The same product is labeled differently over time; category budgets stop meaning anything."],
        ["Unsafe automation", "An AI model that writes categories, amounts or accounts directly can corrupt the budget."],
        ["Opaque credit debt", "Card payments recorded as plain expenses make the debt per card impossible to read."],
        ["Operational risk", "Tokens in scripts, destructive jobs, duplicated inserts after a retry."],
    ], [0.27, 0.73]))

    s.append(P("5. Target Audience / Use Case", h2))
    s.append(P("A single person (or a couple) managing several accounts and credit cards in one currency (EUR) who is comfortable creating "
               "a GitHub repository and a free Supabase project, plus freelancers and teams who want a reference implementation of a "
               "serverless data pipeline with an AI audit step. The system is configured per user with a Phase 0 interview and runs on free "
               "tiers; the only variable cost is the vision model, used only for receipt photos."))
    s.append(P("Data Model", h3))
    s.append(table([
        ["Entity", "Role in the model"],
        ["Accounts", "Spending, savings and credit-card accounts. A trigger derives the payment medium (debit or credit) from the account."],
        ["Categories (versioned)", "Budget buckets with type, period and amount. Changing a budget closes the current row and opens a new one, so history keeps its own budget (SCD2)."],
        ["Labels", "Closed vocabulary with a criterion and keywords. A label lists the categories where it is allowed."],
        ["Ledger", "One row per movement: amount, type, date, account, category, label, payment medium."],
        ["Pendings", "Payloads that could not be recorded, with the error. Resolved overnight, then purged."],
        ["Templates", "Fixed expenses, savings moves and card payments as versioned JSON, resolved by date."],
    ], [0.27, 0.73]))
    s.append(P("Budget Policy", h3))
    s.append(P("One budget amount is entered per period. The monthly view divides it by the months of the period. Yearly categories have "
               "their own view and one-off categories carry no periodic budget."))
    s.append(table([
        ["Period", "Months", "Monthly share", "Where it shows"],
        ["Monthly", "1", "budget", "Monthly budget view"],
        ["Every 2 / 3 / 4 / 6 months", "2 / 3 / 4 / 6", "budget / months", "Monthly budget view"],
        ["Yearly", "12", "n/a (yearly)", "Annual budget view"],
        ["One-off", "none", "n/a", "No periodic budget"],
    ], [0.34, 0.16, 0.22, 0.28]))

    s.append(P("6. Solution Implemented", h2))
    s.append(P("Three tracks, independently deployable but operationally linked. Track 1 removes friction, Track 2 guarantees that every "
               "record ends in the ledger or in a pending, and Track 3 turns the leftovers into learning. Guiding principle: "
               "<b>deterministic rules first, AI second, and AI never writes the budget</b>."))
    s.append(P("Track 1: Capture (iOS Shortcuts)", h3))
    s.append(table([
        ["Shortcut", "Trigger", "What it does"],
        ["Purchases", "Wallet / NFC transaction", "Pick account and categories, then upload a receipt photo or type amount, name and comment per category."],
        ["Manual hub", "Manual", "Income or expense; account, categories, with or without receipt photo; stamped with the system date."],
        ["Fixed expenses", "Manual or time automation", "Up to 7 one-tap fixed expenses, savings deposit / withdrawal and credit card payment."],
    ], [0.18, 0.24, 0.58]))
    s.append(P("Every branch ends in one HTTPS call to the GitHub repository_dispatch endpoint with a typed event "
               "(dynamic expense, photo expense or standardized ingestion) and a small JSON payload."))
    s.append(P("Track 2: Ingestion (GitHub Actions + Python)", h3))
    s.append(table([
        ["Workflow", "Trigger", "Script", "Purpose"],
        ["gasto_dinamico", "repository_dispatch", "ingesta_dinamica.py", "1 to 3 lines; label by category-bounded keyword matching."],
        ["gasto_foto", "repository_dispatch", "ingesta_foto.py", "Receipt photo read by a vision model, glossary override, TOTAL check."],
        ["ingesta_estandarizada", "repository_dispatch", "ingesta_estandarizada.py", "Fixed templates and linked rows (savings, card payment)."],
        ["limpieza_recibos", "cron, every 2 days", "limpieza_recibos.py", "Deletes receipt photos older than 7 days unless a pending still needs them."],
        ["purgar_pendientes", "cron, daily", "purgar_pendientes_procesados.py", "Removes pendings already marked as processed."],
        ["tests", "push / pull request", "pytest + YAML check", "Continuous integration of the whole code base."],
    ], [0.22, 0.21, 0.29, 0.28]))
    s.append(KeepTogether([P("Step-by-Step Decision Tree", h3), fig_tree(), P("Figure 2. How a record is handled once it reaches the workflow.", cap)]))
    s.append(P("Anti-Patterns the Design Prevents", h3))
    s.append(table([
        ["Anti-pattern", "Why it fails"],
        ["Letting the AI pick amounts or categories freely", "One hallucinated category corrupts a budget. Here the model only picks a number from a closed menu built from categories chosen by the user, and amounts are verified against the receipt TOTAL."],
        ["Fire-and-forget integrations", "A failed call vanishes. Here every failure creates a pending record and a Telegram message with the reason."],
        ["Secrets in scripts or Shortcuts", "A leaked token compromises the ledger. Here secrets live only in GitHub Secrets and Supabase Vault; the phone holds an insert-only key."],
        ["Destructive maintenance", "Unattended deletes lose data. Here the routine only INSERTs and marks; a separate job purges what was marked."],
    ], [0.3, 0.7]))

    s.append(P("Track 3: Audit (nightly Claude routine)", h3))
    s.append(P("An unattended routine with the Supabase MCP connector closes the loop every night. It fixes a window of records "
               "(watermark to cap), then runs five phases. Its invariants: the category always rules, only the label may change on "
               "existing rows, nothing is deleted, each pending is inserted with a single statement, and duplicates are detected "
               "before inserting."))
    s.append(table([
        ["Phase", "What happens", "Output"],
        ["0. Context", "Reads the watermark and fixes the cap of the window.", "Window of record ids"],
        ["1. Pendings", "Registers each pending (text, photo or template) with one INSERT and marks it processed.", "Rows in the ledger"],
        ["2. Validate", "Judges each label against its criterion and siblings; corrects with an UPDATE of the label only.", "Audit trail rows"],
        ["3. Glossary", "Extracts generic product keywords and adds them if no label has them.", "New keywords"],
        ["4. Log and notify", "Writes the run log and sends the summary by Telegram and push.", "Run log, message"],
    ], [0.17, 0.58, 0.25]))
    s.append(P("Exception Lifecycle", h3))
    s.append(table([
        ["Stage", "What happens", "Where"],
        ["1. Capture", "The record is sent with the typed event.", "Track 1"],
        ["2. Fail or no match", "A pending is created with the payload and the reason; Telegram reports it.", "Track 2"],
        ["3. Resolve", "The routine registers it, verifies the rows exist and marks it processed.", "Track 3"],
        ["4. Learn", "New keywords reduce the chance of the same miss tomorrow.", "Track 3"],
        ["5. Purge", "A daily job deletes processed pendings; old photos expire after 7 days.", "Track 2"],
    ], [0.22, 0.58, 0.2]))

    s.append(P("7. Technical Logic of Interest", h2))
    items = [
        ("7.1 Deterministic Labeling First, AI Second",
         "The label is resolved by keyword matching against the live vocabulary, bounded to the labels allowed for the chosen category. "
         "The score is the length of the matching keywords, so a specific phrase beats a generic word. Only when nothing matches does the "
         "record become a pending for the nightly audit. It is instant, free and needs no network call."),
        ("7.2 Receipt Reading Verified Against the TOTAL",
         "The vision model receives a numbered menu of label options limited to the categories picked on the phone and returns a number per "
         "product. The glossary overrides the model when keywords recognize the literal receipt text. The sum of lines must match the printed "
         "total within 0.05; otherwise exactly one re-read is requested with the mismatch as a hint, and a second failure becomes a pending "
         "instead of wrong numbers in the budget."),
        ("7.3 Versioned Categories (SCD2)",
         "A category code can have several rows with validity dates; a partial unique index allows only one open row per code. Lookups use "
         "the validity date of the record, so a rent increase never rewrites last year's budget."),
        ("7.4 Linked Rows in One Statement",
         "Savings moves and credit card payments are two rows with opposite signs inserted atomically: payer account minus, destination "
         "account (a savings account or a specific card) plus. Debt per card becomes a plain sum and any number of cards works."),
        ("7.5 Idempotent, Non-Destructive Audit",
         "The routine works on a frozen window (watermark to cap), checks for an equivalent existing record before inserting and never "
         "deletes: it marks. A separate scheduled job, which uses the service key through REST and not the MCP connector, performs the purge."),
        ("7.6 Trust Boundaries",
         "The service key exists only in GitHub Secrets. The phone holds a publishable key that the bucket policy restricts to INSERT. Every "
         "table has row-level security enabled with no policies, so only the service role reads or writes. Telegram credentials live in "
         "Vault and are used by a security-definer function that is not executable by the public roles."),
        ("7.7 Portable by Configuration",
         "Nothing personal is hardcoded: time zone and currency symbol are repository variables, accounts, categories, labels and fixed "
         "expenses come from a setup interview that generates the seed and the templates, and the Shortcuts are published with placeholders."),
    ]
    for t_, p_ in items:
        s.append(P(t_, h3))
        s.append(P(p_))

    s.append(P("8. Result / Impact", h2))
    s.append(P("Results observed in the production instance used daily by the author and in the public template:"))
    s.append(stat_cards([("600+", "ledger records<br/>in production use"), ("36", "automated tests,<br/>CI on every push"),
                         ("8 + 4", "tables with row-level<br/>security + views")]))
    s.append(Spacer(1, 8))
    s.append(table([
        ["Metric", "Value", "Notes"],
        ["Ledger records", "600+", "Real movements recorded through the Shortcuts"],
        ["iOS Shortcuts", "3", "Purchases, manual hub, fixed expenses"],
        ["GitHub workflows", "5 + CI", "3 ingestion, 2 maintenance, 1 test workflow"],
        ["Database", "8 tables, 4 views", "Row-level security on all tables, 1 private bucket"],
        ["Budget periods", "7", "Monthly to yearly plus one-off"],
        ["Default label taxonomy", "40", "Criterion + keywords, extensible per user"],
        ["Automated tests", "36", "Pure logic, cross-checks Shortcut / template / seed / workflow"],
        ["Secrets in code", "0", "Verified by a scan before publication"],
    ], [0.3, 0.22, 0.48]))
    s.append(P("Operational impact", h3))
    s.append(table([
        ["Dimension", "Before (spreadsheet)", "After"],
        ["Capture", "Open file, type fields, often postponed.", "One tap or an NFC payment; photo optional."],
        ["Failures", "Lost silently.", "Every failure becomes a pending with its reason."],
        ["Labeling", "Manual and inconsistent.", "Deterministic matching, audited nightly, glossary grows."],
        ["Budgets", "Static, monthly only.", "Versioned categories, seven periods, live views."],
        ["Credit cards", "Debt estimated by hand.", "Debt and available limit per card, always derived."],
        ["Security", "Credentials spread across files.", "Secrets in Secrets/Vault; insert-only key on the phone."],
    ], [0.18, 0.37, 0.45]))
    s.append(P("The system, the Shortcuts, the scripts and the documentation were delivered as a public template repository. "
               "No time-saving figures are published because they were not measured.", cap))

    s.append(P("9. Technical Fragments", h2))
    s.append(P("9.1 Libraries and Their Role", h3))
    s.append(table([
        ["Library / Technology", "Min. Version", "Role in Project"],
        ["Python", "3.12", "Language of all ingestion and maintenance scripts"],
        ["requests", "2.31+", "HTTP calls to Supabase REST / Storage, Telegram and the vision API"],
        ["PostgreSQL (Supabase)", "17", "Ledger, versioned categories, views, triggers, RLS"],
        ["Supabase Storage / Vault / pg_net", "managed", "Private receipt bucket, secrets, Telegram call from SQL"],
        ["GitHub Actions", "n/a", "Event-driven ingestion, cron maintenance, CI"],
        ["Qwen3-VL (DashScope)", "flash", "Receipt reading through an OpenAI-compatible endpoint"],
        ["Claude + MCP connector", "n/a", "Nightly audit routine with SQL tool access"],
        ["pytest / PyYAML", "8+ / 6+", "Unit and cross-consistency tests, workflow YAML validation"],
    ], [0.34, 0.16, 0.5]))

    s.append(KeepTogether([P("9.2 Execution Flow", h3), fig_flow(), P("Figure 3. Event-driven ingestion with the audit loop behind it.", cap)]))
    s.append(P("9.3 Execution Mode", h3))
    s.append(P("<b>Ingestion:</b> serverless, event-driven; each record starts one short workflow run. <b>Maintenance:</b> two cron "
               "workflows (receipt cleanup every 2 days, pending purge daily). <b>Audit:</b> a scheduled Claude routine that runs "
               "unattended once per night, before the purge."))

    s.append(P("9.4 Key Code Snippets", h3))
    s.append(P("Snippet 1: Keyword matching bounded by category (ingesta_dinamica.py, condensed)", snip))
    s.append(code_block(
"""def resolver_etiqueta_por_keyword(texto, codigo_categoria, etiquetas):
    texto_norm = normalizar(texto)
    mejor, mejor_score = None, 0
    for e in etiquetas:
        if codigo_categoria not in (e.get("posibles_categorias") or []):
            continue                      # the category rules
        score = sum(len(normalizar(kw)) for kw in (e.get("keyword") or [])
                    if normalizar(kw) and normalizar(kw) in texto_norm)
        if score > mejor_score:           # longer match wins
            mejor, mejor_score = e, score
    return (mejor["nombre_etiqueta"], mejor["id_etiqueta"]) if mejor else (None, None)"""))
    s.append(P("Snippet 2: Linked rows for savings and card payments (ingesta_estandarizada.py, condensed)", snip))
    s.append(code_block(
"""def construir_filas_multiples(version, fecha, monto, cuenta, cuenta_destino, comentario):
    monto_abs = abs(importe_a_float(monto))
    categoria = resolver_categoria_o_falla(version["codigo_categoria"], fecha)
    cuentas = {"cuenta": cuenta, "cuenta_destino": cuenta_destino}
    return [{
        "importe": monto_abs * fila["signo"],          # -amount on payer, +amount on destination
        "id_cuenta": resolver_cuenta(fila["id_cuenta"],
                                     cuentas[fila.get("cuenta_payload", "cuenta")]),
        "id_categoria": categoria["id_categoria"],
        "tipo": categoria["tipo"],
        "fecha_operacion": fecha,
    } for fila in version["filas"]]                    # inserted in ONE statement"""))
    s.append(P("Snippet 3: Credit position per card (supabase/setup.sql)", snip))
    s.append(code_block(
"""create or replace view public.vista_credito with (security_invoker = on) as
 select c.id_cuenta, c.nombre_cuenta, t.limite,
        coalesce(-sum(se.importe), 0)                    as deuda,
        t.limite - coalesce(-sum(se.importe), 0)         as credito_disponible
   from cuentas c
   join tarjeta_credito t on t.id_cuenta = c.id_cuenta
   left join seguimiento_efectivo se on se.id_cuenta = c.id_cuenta
  group by c.id_cuenta, c.nombre_cuenta, t.limite;"""))

    s.append(P("9.5 External API Dependencies", h3))
    s.append(table([
        ["API", "Key Endpoints", "Auth Method", "Use"],
        ["GitHub REST", "POST /repos/{owner}/{repo}/dispatches", "Fine-grained token, this repo only", "Trigger ingestion from the phone"],
        ["Supabase REST (PostgREST)", "/rest/v1/{table}", "Service key (Actions only)", "Resolve ids, insert rows, pendings"],
        ["Supabase Storage", "/storage/v1/object/{bucket}/{path}", "Publishable key, insert-only policy", "Receipt upload, read, cleanup"],
        ["Telegram Bot API", "/bot{token}/sendMessage", "Bot token (Secrets / Vault)", "Result and failure messages"],
        ["DashScope (OpenAI-compatible)", "/chat/completions", "API key (Secrets)", "Vision model for receipts"],
    ], [0.22, 0.31, 0.25, 0.22]))

    s.append(P("9.6 Error Handling and Logging", h3))
    s.append(P("Every ingestion script keeps its core in a function that raises and a thin <font face='Courier'>main()</font> that decides: on any "
               "exception it stores a pending record with the payload and the error, sends the reason by Telegram and exits with a "
               "non-zero code so the workflow run is marked failed. Transient AI errors (5xx, 429) are retried a limited number of times; "
               "database errors are not retried, by design, because the pending and the nightly routine cover them. Workflow logs and "
               "the run log table provide the operational trace."))

    s.append(P("10. Privacy and Data Protection Review", h2))
    box = Table([[Paragraph(
        "<b>PRIVACY REVIEW</b><br/>The following elements were replaced by neutral placeholders in the public repository and in this "
        "document:<br/>Supabase project reference and URLs: <font face='Courier'>{{SUPABASE_PROJECT_REF}}</font><br/>GitHub owner, repository "
        "and tokens: <font face='Courier'>{{GITHUB_OWNER}}, {{GITHUB_REPO}}, {{GITHUB_PAT}}</font><br/>Account, card and category names, "
        "Wallet card identifiers: <font face='Courier'>{{ACCOUNT_n}}, {{CREDIT_CARD_n}}, {{CATEGORY_n}}</font><br/>Telegram bot token and "
        "chat identifier: stored only in GitHub Secrets and Supabase Vault.<br/><br/>No real transactions, balances, credentials or "
        "personal identifiers appear in this document or in the repository; figures are aggregate counts only.", cell)]],
        colWidths=[CW])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMBER_BG), ("BOX", (0, 0), (-1, -1), 0.9, AMBER),
                             ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                             ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    s.append(box)

    # keep every snippet title with its code block
    out, i = [], 0
    while i < len(s):
        item = s[i]
        if isinstance(item, Paragraph) and item.style.name == "snip" and i + 1 < len(s):
            out.append(KeepTogether([item, s[i + 1]]))
            i += 2
        else:
            out.append(item)
            i += 1
    doc.build(out)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "docs", "portfolio", f"{DOC_ID}_{VERSION}_Personal_Finance_System.pdf")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    build(out)
    print(os.path.abspath(out))
