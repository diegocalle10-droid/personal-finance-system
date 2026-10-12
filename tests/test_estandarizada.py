# -*- coding: utf-8 -*-
"""Standardized ingestion: row building, linked rows (card payment, savings)
and validity of the shipped example templates. Supabase lookups are patched."""
import json
import os

import pytest

import ingesta_estandarizada as est

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXAMPLE = os.path.join(ROOT, "config", "plantillas_estandarizadas.example.json")

CATEGORIAS = {
    "renta": {"id_categoria": "CT1", "tipo": "coste fijo", "glosa": "Street 1"},
    "creditos": {"id_categoria": "CT2", "tipo": "pago tarjeta", "glosa": None},
    "ahorros": {"id_categoria": "CT3", "tipo": "traspaso", "glosa": None},
    "subscripciones": {"id_categoria": "CT4", "tipo": "coste fijo", "glosa": None},
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


def test_fixed_amount_template():
    filas = [est.construir_fila_simple(est.cargar_version_vigente("subscription_example", "2026-03-01"),
                                       "2026-03-01", None, None, None)]
    assert filas[0]["importe"] == -2.99
    assert filas[0]["id_cuenta"] == "CU000001"
    assert filas[0]["tipo"] == "coste fijo"


def test_variable_amount_applies_sign_and_comma():
    version = est.cargar_version_vigente("phone_example", "2026-03-01")
    fila = est.construir_fila_simple(version, "2026-03-01", "12,5", None, "April bill")
    assert fila["importe"] == -12.5
    assert fila["comentario"] == "April bill"


def test_comment_from_shortcut_is_required():
    version = est.cargar_version_vigente("phone_example", "2026-03-01")
    with pytest.raises(ValueError):
        est.construir_fila_simple(version, "2026-03-01", "10", None, None)


def test_card_payment_creates_two_linked_rows_on_the_chosen_card():
    version = est.cargar_version_vigente("pago_tarjeta", "2026-03-01")
    filas = est.construir_filas_multiples(version, "2026-03-01", "200", "Main bank", "Card B", None)
    assert [f["id_cuenta"] for f in filas] == ["CU1", "CU4"]
    assert [f["importe"] for f in filas] == [-200.0, 200.0]
    assert {f["tipo"] for f in filas} == {"pago tarjeta"}
    assert sum(f["importe"] for f in filas) == 0


def test_card_payment_without_destination_card_fails():
    version = est.cargar_version_vigente("pago_tarjeta", "2026-03-01")
    with pytest.raises(ValueError):
        est.construir_filas_multiples(version, "2026-03-01", "200", "Main bank", None, None)


def test_savings_deposit_nets_to_zero_and_needs_comment():
    version = est.cargar_version_vigente("ahorro_aporte", "2026-03-01")
    filas = est.construir_filas_multiples(version, "2026-03-01", "50", "Main bank", None, "Monthly saving")
    assert [f["importe"] for f in filas] == [-50.0, 50.0]
    with pytest.raises(ValueError):
        est.construir_filas_multiples(version, "2026-03-01", "50", "Main bank", None, None)


def test_unknown_type_and_missing_date():
    with pytest.raises(ValueError):
        est.cargar_version_vigente("nope", "2026-03-01")
    with pytest.raises(ValueError):
        est.procesar_ingesta_estandarizada("rent", None, "1", None, None)


def test_expired_version_is_not_valid():
    with pytest.raises(ValueError):
        est.cargar_version_vigente("rent", "2025-01-01")  # before fecha_inicio


def test_no_second_currency_left_in_code():
    src = open(os.path.join(ROOT, "scripts", "ingesta_estandarizada.py"), encoding="utf-8").read()
    assert "monto_eur" not in src.lower() and "importe_eur" not in src
