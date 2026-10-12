# -*- coding: utf-8 -*-
"""Standardized ingestion: fixed expenses, linked rows (card payment, savings)
and validity of the shipped example templates. Supabase lookups are patched."""
import json
import os
import re

import pytest

import ingesta_estandarizada as est

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXAMPLE = os.path.join(ROOT, "config", "plantillas_estandarizadas.example.json")

CATEGORIAS = {
    "rent": {"id_categoria": "CT1", "tipo": "coste fijo", "glosa": "Street 1"},
    "credit_card_payments": {"id_categoria": "CT2", "tipo": "pago tarjeta", "glosa": None},
    "savings": {"id_categoria": "CT3", "tipo": "traspaso", "glosa": None},
    "subscriptions": {"id_categoria": "CT4", "tipo": "coste fijo", "glosa": None},
    "salary": {"id_categoria": "CT5", "tipo": "ingreso", "glosa": None},
}
CUENTAS = {"Main bank": "CU1", "Card A": "CU3", "Card B": "CU4"}


@pytest.fixture(autouse=True)
def patched(monkeypatch):
    monkeypatch.setattr(est, "PLANTILLAS_PATH", EXAMPLE)
    monkeypatch.setattr(est, "resolver_categoria", lambda codigo, fecha: CATEGORIAS.get(codigo))
    monkeypatch.setattr(est, "resolver_id_cuenta_por_nombre", lambda n: CUENTAS.get(n))


def test_example_templates_are_valid_json_with_required_fields():
    with open(EXAMPLE, encoding="utf-8") as f:
        data = json.load(f)
    for tipo, versiones in data.items():
        assert isinstance(versiones, list) and versiones, tipo
        for v in versiones:
            assert "fecha_inicio" in v and "codigo_categoria" in v and "id_etiqueta" in v, tipo
            assert "filas" in v or "nombre_operacion" in v, tipo


def test_every_simple_example_is_a_fixed_expense():
    """Design rule: a fixed expense has a fixed amount AND a fixed account, so the
    Shortcut only sends tipo_ingesta + fecha."""
    data = json.load(open(EXAMPLE, encoding="utf-8"))
    for tipo, versiones in data.items():
        for v in versiones:
            if "filas" in v:
                continue
            assert v.get("importe_fijo") not in (None, 0), tipo
            assert v.get("id_cuenta"), tipo
            assert "comentario_fijo" in v or "comentario_fuente" in v, tipo


def test_fixed_expense_needs_only_type_and_date():
    version = est.cargar_version_vigente("subscription", "2026-03-01")
    fila = est.construir_fila_simple(version, "2026-03-01", None, None, None)
    assert fila["importe"] == -2.99
    assert fila["id_cuenta"] == "CU000001"
    assert fila["tipo"] == "coste fijo"
    assert fila["comentario"] == "Monthly cloud storage"


def test_fixed_income_keeps_positive_sign():
    version = est.cargar_version_vigente("salary", "2026-03-01")
    fila = est.construir_fila_simple(version, "2026-03-01", None, None, None)
    assert fila["importe"] == 1500.0 and fila["tipo"] == "ingreso"


def test_rent_comment_comes_from_category_glosa():
    version = est.cargar_version_vigente("rent", "2026-03-01")
    fila = est.construir_fila_simple(version, "2026-03-01", None, None, None)
    assert fila["comentario"] == "Street 1"
    assert fila["importe"] == -500.0


def test_variable_amount_template_still_supported_and_requires_monto():
    version = {"fecha_inicio": "2026-01-01", "fecha_fin": None, "nombre_operacion": "x", "id_cuenta": "CU1",
               "codigo_categoria": "rent", "id_etiqueta": "ET1", "importe_fijo": None, "signo": -1,
               "comentario_fijo": "c"}
    assert est.construir_fila_simple(version, "2026-03-01", "12,5", None, None)["importe"] == -12.5
    with pytest.raises(ValueError):
        est.construir_fila_simple(version, "2026-03-01", None, None, None)


def test_card_payment_creates_two_linked_rows_on_the_chosen_card():
    version = est.cargar_version_vigente("credit_card_payment", "2026-03-01")
    filas = est.construir_filas_multiples(version, "2026-03-01", "200", "Main bank", "Card B", None)
    assert [f["id_cuenta"] for f in filas] == ["CU1", "CU4"]
    assert [f["importe"] for f in filas] == [-200.0, 200.0]
    assert {f["tipo"] for f in filas} == {"pago tarjeta"}
    assert sum(f["importe"] for f in filas) == 0


def test_card_payment_without_destination_card_fails():
    version = est.cargar_version_vigente("credit_card_payment", "2026-03-01")
    with pytest.raises(ValueError):
        est.construir_filas_multiples(version, "2026-03-01", "200", "Main bank", None, None)


def test_savings_deposit_nets_to_zero_and_needs_comment():
    version = est.cargar_version_vigente("savings_deposit", "2026-03-01")
    filas = est.construir_filas_multiples(version, "2026-03-01", "50", "Main bank", None, "Monthly saving")
    assert [f["importe"] for f in filas] == [-50.0, 50.0]
    assert [f["id_cuenta"] for f in filas] == ["CU1", "CU000004"]
    with pytest.raises(ValueError):
        est.construir_filas_multiples(version, "2026-03-01", "50", "Main bank", None, None)


def test_savings_withdrawal_goes_to_the_chosen_account():
    version = est.cargar_version_vigente("savings_withdrawal", "2026-03-01")
    filas = est.construir_filas_multiples(version, "2026-03-01", "50", "Main bank", None, "Need cash")
    assert [f["importe"] for f in filas] == [-50.0, 50.0]
    assert [f["id_cuenta"] for f in filas] == ["CU000004", "CU1"]


def test_unknown_type_and_missing_date():
    with pytest.raises(ValueError):
        est.cargar_version_vigente("nope", "2026-03-01")
    with pytest.raises(ValueError):
        est.procesar_ingesta_estandarizada("rent", None, None, None, None)


def test_expired_version_is_not_valid():
    with pytest.raises(ValueError):
        est.cargar_version_vigente("rent", "2025-01-01")  # before fecha_inicio


def test_no_second_currency_left_in_code():
    src = open(os.path.join(ROOT, "scripts", "ingesta_estandarizada.py"), encoding="utf-8").read()
    assert "monto_eur" not in src.lower() and "importe_eur" not in src


def test_example_template_label_ids_exist_in_default_seed():
    """The example templates must point to labels that the default seed creates."""
    seed = open(os.path.join(ROOT, "supabase", "seed_etiquetas_default.sql"), encoding="utf-8").read()
    seed_ids = set(re.findall(r"\('(ET\d{6})'", seed))
    with open(EXAMPLE, encoding="utf-8") as f:
        data = json.load(f)
    used = {v["id_etiqueta"] for versiones in data.values() for v in versiones}
    assert used <= seed_ids, used - seed_ids
