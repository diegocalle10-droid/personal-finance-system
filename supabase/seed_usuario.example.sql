-- =====================================================================
-- seed_usuario.example.sql: what the Phase 0 interview generates for you.
-- Copy to seed_usuario.sql (git-ignored), replace values, run in SQL Editor
-- AFTER setup.sql and seed_etiquetas_default.sql. Single currency (EUR).
-- =====================================================================

-- Accounts. naturaleza: disponible | ahorro | credito
--           medio_pago: debito | credito (credit cards only)
insert into public.cuentas (nombre_cuenta, naturaleza, medio_pago) values
  ('Main bank',   'disponible', 'debito'),
  ('Cash',        'disponible', 'debito'),
  ('Credit card', 'credito',    'credito'),
  ('Savings',     'ahorro',     'debito')
on conflict (nombre_cuenta) do nothing;

-- Credit cards (one row per card account; limit in EUR)
insert into public.tarjeta_credito (id_cuenta, limite)
select id_cuenta, 1500 from public.cuentas where nombre_cuenta = 'Credit card'
on conflict (id_cuenta) do nothing;

-- Categories (default set: every code below is referenced by the default labels).
--   tipo:         ingreso | gasto | coste fijo | traspaso | ajuste patrimonial | pago tarjeta
--   periodicidad: mensual | bimensual | trimestral | cuatrimestral | semestral | anual | puntual
--   presupuesto_base is the budget for ONE period (e.g. trimestral 90 = 30 / month).
--   fecha_fin null = active. To change a budget later: close the row (set
--   fecha_fin) and insert a new one with the same codigo_categoria.
-- Required by the system: 'ingresos_varios' (used by the manual income flow),
-- one 'traspaso' (savings), one 'pago tarjeta' (card payments), one 'ajuste patrimonial'.
insert into public.categorias (codigo_categoria, nombre_categoria, tipo, periodicidad, presupuesto_base, fecha_inicio, glosa) values
  ('renta', 'renta', 'coste fijo', 'mensual', 500, '2026-01-01', 'Street 1, 2nd floor'),
  ('alimentacion', 'alimentacion', 'gasto', 'mensual', 250, '2026-01-01', null),
  ('transporte', 'transporte', 'gasto', 'mensual', 40, '2026-01-01', null),
  ('entretenimiento', 'entretenimiento', 'gasto', 'mensual', 50, '2026-01-01', null),
  ('salud_belleza', 'salud y belleza', 'gasto', 'bimensual', 80, '2026-01-01', null),
  ('deporte', 'deporte', 'gasto', 'mensual', 30, '2026-01-01', null),
  ('hogar', 'hogar', 'gasto', 'mensual', 50, '2026-01-01', null),
  ('subscripciones', 'subscripciones', 'coste fijo', 'mensual', 35, '2026-01-01', null),
  ('gimnasio', 'gimnasio', 'coste fijo', 'mensual', 30, '2026-01-01', null),
  ('seguros', 'seguros', 'gasto', 'trimestral', 90, '2026-01-01', null),
  ('viajes', 'viajes', 'gasto', 'semestral', 600, '2026-01-01', null),
  ('ropa_calzado', 'ropa y calzado', 'gasto', 'anual', 300, '2026-01-01', null),
  ('educacion', 'educacion', 'gasto', 'anual', 500, '2026-01-01', null),
  ('gastos_varios', 'gastos varios', 'gasto', 'anual', 400, '2026-01-01', null),
  ('impuestos_tasas', 'impuestos y tasas', 'gasto', 'anual', 500, '2026-01-01', null),
  ('regularizacion_papeles', 'regularizacion y papeles', 'gasto', 'anual', 300, '2026-01-01', null),
  ('regalos', 'regalos', 'gasto', 'puntual', 200, '2026-01-01', null),
  ('ayuda_familiar', 'ayuda familiar', 'gasto', 'puntual', 100, '2026-01-01', null),
  ('mudanza', 'mudanza', 'gasto', 'puntual', 500, '2026-01-01', null),
  ('salario', 'salario', 'ingreso', 'mensual', 1500, '2026-01-01', null),
  ('ingresos_varios', 'ingresos varios', 'ingreso', 'puntual', 0, '2026-01-01', null),
  ('ahorros', 'ahorros', 'traspaso', 'mensual', 0, '2026-01-01', null),
  ('creditos', 'creditos', 'pago tarjeta', 'mensual', 0, '2026-01-01', null),
  ('ajustes_patrimonial', 'ajustes patrimonial', 'ajuste patrimonial', 'puntual', 0, '2026-01-01', null)
on conflict do nothing;
