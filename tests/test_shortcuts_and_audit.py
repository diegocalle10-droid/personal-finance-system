# -*- coding: utf-8 -*-
"""Cross-checks between Shortcuts, templates, seeds, workflows and scripts,
plus regression tests for the storage-cleanup path bug."""
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def load(rel):
    return json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))


def read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


def category_codes_in_user_seed():
    return set(re.findall(r"^\s*\('([a-z_]+)',\s*'", read("supabase/seed_usuario.example.sql"), re.M))


def test_shortcut_event_types_match_workflows():
    triggers = set()
    for p in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
        w = yaml.safe_load(open(p, encoding="utf-8"))
        on = w.get("on") or w.get(True)
        rd = on.get("repository_dispatch") if isinstance(on, dict) else None
        if rd:
            triggers |= set(rd["types"])
    text = "".join(read("shortcuts/%s.json" % n) for n in ("Manufinanza", "Compras", "Gasto_fijo"))
    used = set(re.findall(r'event_type\\?"\s*:\s*\\?"([a-z_]+)', text))
    assert used and used <= triggers, used - triggers


def test_fixed_expense_shortcut_structure():
    """Literal keys (savings) must be templates; every fixed-expense slot must be
    a placeholder pair (label + key) so Phase 0 can fill it."""
    texts, labels = [], []

    def walk(n):
        if isinstance(n, dict):
            t = (n.get("parameters") or {}).get("TextActionText")
            if n.get("action") == "Text" and isinstance(t, str):
                texts.append(t)
            if "option" in n:
                labels.append(n["option"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(load("shortcuts/Gasto_fijo.json"))
    templates = set(load("config/plantillas_estandarizadas.example.json"))
    literal = {t for t in texts if not t.startswith("{{")}
    assert literal == {"savings_deposit", "savings_withdrawal", "credit_card_payment"}
    assert literal <= templates
    slots = [t for t in texts if re.fullmatch(r"\{\{FIXED_EXPENSE_\d+_KEY\}\}", t)]
    slot_labels = [l for l in labels if re.fullmatch(r"\{\{FIXED_EXPENSE_\d+_LABEL\}\}", l)]
    assert len(slots) == len(slot_labels) >= 6


def test_estandarizada_payload_fields_are_read_by_workflow():
    wf = read(".github/workflows/ingesta_estandarizada.yml")
    sent = set()

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("client_payload"), dict):
                sent.update(n["client_payload"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(load("shortcuts/Gasto_fijo.json"))
    assert sent
    for field in sent:
        assert "client_payload." + field in wf, field


def test_all_placeholders_are_documented():
    from list_placeholders import placeholders
    doc = read("shortcuts/PLACEHOLDERS.md")
    for name in placeholders():
        generic = re.sub(r"_\d+(?=_|$)", "_n", name)
        base = re.sub(r"_\d+$", "", name)
        assert name in doc or generic in doc or base in doc, name


def test_no_secret_like_values_in_shortcuts():
    pat = re.compile(r"github_pat_[A-Za-z0-9_]{10}|ghp_[A-Za-z0-9]{10}|sb_(publishable|secret)_[A-Za-z0-9]|"
                     r"[a-z0-9]{20}\.supabase\.co|eyJ[A-Za-z0-9_-]{20}")
    for p in glob.glob(os.path.join(ROOT, "shortcuts", "*.json")):
        assert not pat.search(open(p, encoding="utf-8").read()), p


def test_default_label_categories_exist_in_example_seed():
    used = set()
    for line in read("supabase/seed_etiquetas_default.sql").splitlines():
        found = re.findall(r"'(\[[^\]]*\])'::jsonb", line)
        if len(found) == 2:  # keywords, posibles_categorias
            used |= set(json.loads(found[1]))
    codes = category_codes_in_user_seed()
    assert used and used <= codes, used - codes


def test_template_categories_exist_in_example_seed():
    codes = category_codes_in_user_seed()
    for versiones in load("config/plantillas_estandarizadas.example.json").values():
        for v in versiones:
            assert v["codigo_categoria"] in codes, v["codigo_categoria"]
    assert "other_income" in codes  # required by the manual income flow


def test_cleanup_keeps_referenced_photos_even_with_bucket_prefix(monkeypatch):
    import limpieza_recibos as lr
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    new = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    objetos = [
        {"name": "referenced.jpg", "created_at": old},
        {"name": "orphan.jpg", "created_at": old},
        {"name": "recent.jpg", "created_at": new},
        {"name": ".emptyFolderPlaceholder", "created_at": None},
    ]
    deleted = {}

    class Resp:
        ok = True

    def fake_delete(bucket, names):
        deleted["names"] = names
        return Resp()

    monkeypatch.setattr(lr, "listar_objetos_storage", lambda b: objetos)
    monkeypatch.setattr(lr, "listar_fotos_pendientes_de_borrado", lambda: {"recibos/referenced.jpg"})
    monkeypatch.setattr(lr, "borrar_objetos_storage", fake_delete)
    lr.main()
    assert deleted["names"] == ["orphan.jpg"]


def test_nombre_en_bucket():
    import limpieza_recibos as lr
    assert lr.nombre_en_bucket("recibos/1.jpg") == "1.jpg"
    assert lr.nombre_en_bucket("1.jpg") == "1.jpg"


def test_missing_templates_file_has_actionable_message(monkeypatch, tmp_path):
    import ingesta_estandarizada as est
    monkeypatch.setattr(est, "PLANTILLAS_PATH", str(tmp_path / "nope.json"))
    with pytest.raises(ValueError, match="Phase 0"):
        est.cargar_version_vigente("rent", "2026-01-01")


def test_dynamic_flow_builds_expected_rows(monkeypatch):
    import ingesta_dinamica as dyn
    monkeypatch.setattr(dyn, "resolver_id_cuenta_por_nombre", lambda n: "CU000001")
    monkeypatch.setattr(
        dyn, "resolver_categoria",
        lambda c, f: {"id_categoria": "CT1", "tipo": "gasto"} if c == "groceries"
        else {"id_categoria": "CT2", "tipo": "ingreso"})
    monkeypatch.setattr(dyn, "listar_etiquetas_para_matcher", lambda: [
        {"id_etiqueta": "ET3", "nombre_etiqueta": "groceries", "keyword": ["leche"],
         "posibles_categorias": ["groceries"]},
        {"id_etiqueta": "ET16", "nombre_etiqueta": "salary", "keyword": ["nomina"],
         "posibles_categorias": ["other_income"]},
    ])
    captured = {}

    class Resp:
        ok = True

        def json(self):
            return [dict(f, id_operacion="SE000001") for f in captured["filas"]]

    def fake_insert(filas):
        captured["filas"] = filas
        return Resp()

    monkeypatch.setattr(dyn, "insertar_filas", fake_insert)
    lineas = json.dumps([
        {"categoria": "groceries", "importe": "2,5", "nombre_operacion": "Leche", "comentario": ""},
        {"categoria": "other_income", "importe": "10", "nombre_operacion": "Nomina", "comentario": "x"},
    ])
    _, etiquetas, fecha = dyn.procesar_gasto_dinamico("Main bank", lineas, "2026-10-05")
    assert [f["importe"] for f in captured["filas"]] == [-2.5, 10.0]
    assert etiquetas == ["groceries", "salary"] and fecha == "2026-10-05"
    assert all("medio_pago" not in f for f in captured["filas"])  # set by the DB trigger


def test_dynamic_accepts_date_inside_lines_as_fallback(monkeypatch):
    import ingesta_dinamica as dyn
    monkeypatch.setattr(dyn, "resolver_id_cuenta_por_nombre", lambda n: "CU000001")
    monkeypatch.setattr(dyn, "resolver_categoria", lambda c, f: {"id_categoria": "CT1", "tipo": "gasto"})
    monkeypatch.setattr(dyn, "listar_etiquetas_para_matcher", lambda: [
        {"id_etiqueta": "ET3", "nombre_etiqueta": "groceries", "keyword": ["leche"],
         "posibles_categorias": ["groceries"]}])
    seen = {}

    class Resp:
        ok = True

        def json(self):
            return [dict(f, id_operacion="SE000001") for f in seen["filas"]]

    def fake_insert(filas):
        seen["filas"] = filas
        return Resp()

    monkeypatch.setattr(dyn, "insertar_filas", fake_insert)
    lineas = json.dumps([{"fecha": "2026-09-01", "categoria": "groceries", "importe": "1",
                          "nombre_operacion": "leche", "comentario": ""}])
    _, _, fecha = dyn.procesar_gasto_dinamico("Main bank", lineas, None)
    assert fecha == "2026-09-01"
    assert seen["filas"][0]["fecha_operacion"] == "2026-09-01"


def test_shortcut_sources_are_clean_and_consistent():
    import plistlib
    import edit_shortcuts as es
    files = sorted(glob.glob(os.path.join(ROOT, "shortcuts", "source", "*.shortcut")))
    assert len(files) == 3
    for p in files:
        pl = plistlib.load(open(p, "rb"))
        assert es.validate(pl, os.path.basename(p)) == [], p
        text = json.dumps(pl, ensure_ascii=False, default=lambda o: "<bytes>")
        for word in ("completar", "Aporte de ahorro", "Pago de tarjeta", "Selecciona", "ingresos_varios"):
            assert word not in text, (p, word)
        for t in pl.get("WFWorkflowTriggers", []):
            assert t["WFTriggerSerializedParameters"]["WFWalletCards"] == []


def test_manufinanza_does_not_ask_or_send_a_date():
    text = read("shortcuts/Manufinanza.json")
    assert '"fecha"' not in text and "Formatted Date" not in text
