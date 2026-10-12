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


def test_fixed_expense_keys_exist_as_templates():
    keys = set()

    def walk(n):
        if isinstance(n, dict):
            t = (n.get("parametros") or {}).get("TextActionText")
            if n.get("accion") == "Texto" and isinstance(t, str):
                keys.add(t)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(load("shortcuts/Gasto_fijo.json"))
    templates = set(load("config/plantillas_estandarizadas.example.json"))
    assert keys and keys <= templates, keys - templates


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
        base = re.sub(r"_\d+$", "", name)
        assert base in doc or name in doc, name


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
    assert "ingresos_varios" in codes  # required by the manual income flow


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
        lambda c, f: {"id_categoria": "CT1", "tipo": "gasto"} if c == "alimentacion"
        else {"id_categoria": "CT2", "tipo": "ingreso"})
    monkeypatch.setattr(dyn, "listar_etiquetas_para_matcher", lambda: [
        {"id_etiqueta": "ET3", "nombre_etiqueta": "despensa", "keyword": ["leche"],
         "posibles_categorias": ["alimentacion"]},
        {"id_etiqueta": "ET16", "nombre_etiqueta": "salario", "keyword": ["nomina"],
         "posibles_categorias": ["ingresos_varios"]},
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
        {"categoria": "alimentacion", "importe": "2,5", "nombre_operacion": "Leche", "comentario": ""},
        {"categoria": "ingresos_varios", "importe": "10", "nombre_operacion": "Nomina", "comentario": "x"},
    ])
    _, etiquetas, fecha = dyn.procesar_gasto_dinamico("Main bank", lineas, "2026-10-05")
    assert [f["importe"] for f in captured["filas"]] == [-2.5, 10.0]
    assert etiquetas == ["despensa", "salario"] and fecha == "2026-10-05"
    assert all("medio_pago" not in f for f in captured["filas"])  # set by the DB trigger
