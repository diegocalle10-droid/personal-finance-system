# -*- coding: utf-8 -*-
"""Pure-logic tests: label matching, normalization, parsing and verification."""
import motor_supabase as motor
import ingesta_dinamica as dinamica
import ingesta_foto as foto


def test_normalizar_strips_accents_case_and_spaces():
    assert motor.normalizar("  Pechuga   de POLLO ") == "pechuga de pollo"
    assert motor.normalizar("Café") == "cafe"
    assert motor.normalizar(None) == ""


def test_signo_por_tipo():
    assert motor.resolver_signo("ingreso") == 1
    assert motor.resolver_signo("gasto") == -1
    assert motor.resolver_signo("pago tarjeta") == -1
    assert motor.resolver_signo("traspaso") is None


def test_importe_accepts_comma_decimal():
    assert dinamica.normalizar_importe("3,3") == 3.3
    assert dinamica.normalizar_importe("3.3") == 3.3


ETIQUETAS = [
    {"id_etiqueta": "ET1", "nombre_etiqueta": "despensa",
     "keyword": ["pollo", "pechuga de pollo", "leche"], "posibles_categorias": ["alimentacion"]},
    {"id_etiqueta": "ET2", "nombre_etiqueta": "comida fuera",
     "keyword": ["pollo a la brasa", "pizza"], "posibles_categorias": ["alimentacion", "entretenimiento"]},
    {"id_etiqueta": "ET3", "nombre_etiqueta": "farmacia",
     "keyword": ["pollo"], "posibles_categorias": ["salud_belleza"]},
]


def test_matcher_prefers_longest_keyword_match():
    nombre, id_ = dinamica.resolver_etiqueta_por_keyword("Pechuga de POLLO", "alimentacion", ETIQUETAS)
    assert (nombre, id_) == ("despensa", "ET1")


def test_matcher_is_bounded_by_category():
    nombre, _ = dinamica.resolver_etiqueta_por_keyword("pollo", "salud_belleza", ETIQUETAS)
    assert nombre == "farmacia"


def test_matcher_returns_none_without_match():
    assert dinamica.resolver_etiqueta_por_keyword("zzz", "alimentacion", ETIQUETAS) == (None, None)
    assert dinamica.resolver_etiqueta_por_keyword("", "alimentacion", ETIQUETAS) == (None, None)


def test_parsear_categorias_shapes():
    assert foto.parsear_categorias('["alimentacion", "hogar"]') == ["alimentacion", "hogar"]
    assert foto.parsear_categorias("[\"alimentacion','salud_belleza\"]") == ["alimentacion", "salud_belleza"]
    assert foto.parsear_categorias("alimentacion; hogar | deporte") == ["alimentacion", "hogar", "deporte"]
    assert foto.parsear_categorias(None) == []


def test_verificar_total():
    ok, suma, total = foto.verificar_total({"lineas": [{"importe": 1.25}, {"importe": 2.40}], "total": 3.65})
    assert ok and suma == 3.65 and total == 3.65
    ok, _, _ = foto.verificar_total({"lineas": [{"importe": 1.25}], "total": 3.65})
    assert not ok
    # No readable total on the ticket: never blocks
    ok, _, total = foto.verificar_total({"lineas": [{"importe": 1.0}]})
    assert ok and total is None
