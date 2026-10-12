-- =====================================================================
-- seed_usuario.example.sql: what the Phase 0 interview generates for you.
-- Copy to seed_usuario.sql (git-ignored), replace values, run in SQL Editor
-- AFTER setup.sql and seed_etiquetas_default.sql. Single currency (EUR).
--
-- Enum values of the schema are stored in Spanish and never shown to end users:
--   tipo:         ingreso (income) | gasto (expense) | coste fijo (fixed cost) | traspaso (transfer)
--                 | ajuste patrimonial (balance adjustment) | pago tarjeta (card payment)
--   periodicidad: mensual (monthly) | bimensual (every 2 months) | trimestral (quarterly)
--                 | cuatrimestral (every 4 months) | semestral (every 6 months) | anual (yearly)
--                 | puntual (one-off, no periodic budget)
--   naturaleza:   disponible (spending) | ahorro (savings) | credito (credit card)
-- =====================================================================

-- Accounts. medio_pago: debito (debit) | credito (credit, cards only)
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
--   presupuesto_base is the budget for ONE period (e.g. quarterly 90 = 30 / month).
--   fecha_fin null = active. To change a budget later: close the row (set
--   fecha_fin) and insert a new one with the same codigo_categoria.
-- Required by the system: 'other_income' (used by the manual income flow),
-- one 'traspaso' (savings), one 'pago tarjeta' (card payments), one 'ajuste patrimonial'.
insert into public.categorias (codigo_categoria, nombre_categoria, tipo, periodicidad, presupuesto_base, fecha_inicio, glosa) values
  ('rent', 'rent', 'coste fijo', 'mensual', 500, '2026-01-01', 'Street 1, 2nd floor'),
  ('groceries', 'groceries', 'gasto', 'mensual', 250, '2026-01-01', null),
  ('transport', 'transport', 'gasto', 'mensual', 40, '2026-01-01', null),
  ('entertainment', 'entertainment', 'gasto', 'mensual', 50, '2026-01-01', null),
  ('health_beauty', 'health and beauty', 'gasto', 'bimensual', 80, '2026-01-01', null),
  ('sport', 'sport', 'gasto', 'mensual', 30, '2026-01-01', null),
  ('home', 'home', 'gasto', 'mensual', 50, '2026-01-01', null),
  ('subscriptions', 'subscriptions', 'coste fijo', 'mensual', 35, '2026-01-01', null),
  ('gym', 'gym', 'coste fijo', 'mensual', 30, '2026-01-01', null),
  ('insurance', 'insurance', 'gasto', 'trimestral', 90, '2026-01-01', null),
  ('travel', 'travel', 'gasto', 'semestral', 600, '2026-01-01', null),
  ('clothing', 'clothing', 'gasto', 'anual', 300, '2026-01-01', null),
  ('education', 'education', 'gasto', 'anual', 500, '2026-01-01', null),
  ('miscellaneous', 'miscellaneous', 'gasto', 'anual', 400, '2026-01-01', null),
  ('taxes_fees', 'taxes and fees', 'gasto', 'anual', 500, '2026-01-01', null),
  ('paperwork', 'paperwork', 'gasto', 'anual', 300, '2026-01-01', null),
  ('gifts', 'gifts', 'gasto', 'puntual', 200, '2026-01-01', null),
  ('family_support', 'family support', 'gasto', 'puntual', 100, '2026-01-01', null),
  ('moving', 'moving', 'gasto', 'puntual', 500, '2026-01-01', null),
  ('salary', 'salary', 'ingreso', 'mensual', 1500, '2026-01-01', null),
  ('other_income', 'other income', 'ingreso', 'puntual', 0, '2026-01-01', null),
  ('savings', 'savings', 'traspaso', 'mensual', 0, '2026-01-01', null),
  ('credit_card_payments', 'credit card payments', 'pago tarjeta', 'mensual', 0, '2026-01-01', null),
  ('balance_adjustments', 'balance adjustments', 'ajuste patrimonial', 'puntual', 0, '2026-01-01', null)
on conflict do nothing;
