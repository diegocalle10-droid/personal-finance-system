-- =====================================================================
-- setup.sql: full schema, no data. Idempotent (safe to re-run).
-- Single currency (EUR). Run in Supabase -> SQL Editor, then run
-- seed_etiquetas_default.sql and your seed_usuario.sql (Phase 0 output).
-- =====================================================================

-- 0) Extensions -------------------------------------------------------
create extension if not exists pg_net;
create extension if not exists pgcrypto;
create extension if not exists "uuid-ossp";
-- supabase_vault is enabled by default on Supabase projects.

-- 1) Sequences (prefixed text IDs: CT000001, CU000001, ...) -----------
create sequence if not exists public.categorias_id_seq;
create sequence if not exists public.cuentas_id_seq;
create sequence if not exists public.etiquetas_id_seq;
create sequence if not exists public.seguimiento_efectivo_id_seq;
create sequence if not exists public.registros_pendientes_id_seq;

-- 2) Tables -----------------------------------------------------------
create table if not exists public.categorias (
  id_categoria     text primary key default ('CT' || lpad(nextval('public.categorias_id_seq')::text, 6, '0')),
  codigo_categoria text not null,
  nombre_categoria text not null,
  tipo             text not null check (tipo in ('ingreso','gasto','coste fijo','traspaso','ajuste patrimonial','pago tarjeta')),
  periodicidad     text not null check (periodicidad in
                     ('mensual','bimensual','trimestral','cuatrimestral','semestral','anual','puntual')),
  -- Months covered by one budget period; NULL for one-off (puntual) categories.
  meses_periodo    smallint generated always as (
                     case periodicidad
                       when 'mensual' then 1 when 'bimensual' then 2 when 'trimestral' then 3
                       when 'cuatrimestral' then 4 when 'semestral' then 6 when 'anual' then 12
                     end) stored,
  presupuesto_base numeric(12,2) check (presupuesto_base is null or presupuesto_base >= 0),
  fecha_inicio     date not null,
  fecha_fin        date,
  estado           text generated always as (case when fecha_fin is null then 'vigente' else 'inactiva' end) stored,
  glosa            text,
  check (fecha_fin is null or fecha_fin > fecha_inicio)
);
-- Versioned categories: only one open (fecha_fin null) row per codigo_categoria.
create unique index if not exists categorias_activa_por_codigo
  on public.categorias (codigo_categoria) where fecha_fin is null;

create table if not exists public.cuentas (
  id_cuenta     text primary key default ('CU' || lpad(nextval('public.cuentas_id_seq')::text, 6, '0')),
  nombre_cuenta text not null unique,
  naturaleza    text not null check (naturaleza in ('disponible','ahorro','credito')),
  estado        text not null default 'activa' check (estado in ('activa','inactiva')),
  medio_pago    text not null check (medio_pago in ('credito','debito'))
);

create table if not exists public.etiquetas (
  id_etiqueta         text primary key default ('ET' || lpad(nextval('public.etiquetas_id_seq')::text, 6, '0')),
  nombre_etiqueta     text not null unique,
  estado              text not null default 'activa' check (estado in ('activa','inactiva')),
  keyword             jsonb,
  posibles_categorias jsonb,
  criterio            text
);

create table if not exists public.tarjeta_credito (
  id_cuenta text primary key references public.cuentas(id_cuenta),
  limite    numeric(12,2) not null check (limite >= 0)
);

create table if not exists public.seguimiento_efectivo (
  id_operacion     text primary key default ('SE' || lpad(nextval('public.seguimiento_efectivo_id_seq')::text, 6, '0')),
  nombre_operacion text not null,
  importe          numeric(12,2) not null check (importe <> 0),
  tipo             text not null check (tipo in ('ingreso','gasto','coste fijo','traspaso','ajuste patrimonial','pago tarjeta')),
  fecha_operacion  timestamptz not null,
  id_cuenta        text not null references public.cuentas(id_cuenta),
  id_categoria     text not null references public.categorias(id_categoria),
  id_etiqueta      text not null references public.etiquetas(id_etiqueta),
  comentario       text,
  medio_pago       text not null check (medio_pago in ('credito','debito'))
);

create table if not exists public.registros_pendientes (
  id_pendiente     text primary key default ('RP' || lpad(nextval('public.registros_pendientes_id_seq')::text, 6, '0')),
  origen           text not null check (origen in ('gasto_dinamico','gasto_foto','ingesta_estandarizada')),
  payload          jsonb not null,
  foto_bucket_path text,
  error_detalle    text,
  creado_en        timestamptz not null default now(),
  estado           text not null default 'pendiente' check (estado in ('pendiente','procesado')),
  procesado_nota   text
);

create table if not exists public.auditoria_cambios (
  id                  bigint generated always as identity primary key,
  registrado_en       timestamptz not null default now(),
  id_operacion        text not null,
  id_etiqueta_antes   text not null,
  id_etiqueta_despues text not null,
  keyword_anadida     text,
  motivo              text not null
);

create table if not exists public.rutina_nocturna_log (
  id                   bigint generated always as identity primary key,
  ejecutada_en         timestamptz not null default now(),
  ultimo_id_auditado   text not null,
  filas_auditadas      integer not null default 0,
  etiquetas_corregidas integer not null default 0,
  keywords_nuevas      integer not null default 0,
  pendientes_resueltos integer not null default 0,
  resumen              text
);

-- 3) RLS: enabled everywhere, no policies on public tables ------------
-- Only service_role (GitHub Actions / nightly routine) reads and writes.
alter table public.categorias            enable row level security;
alter table public.cuentas               enable row level security;
alter table public.etiquetas             enable row level security;
alter table public.tarjeta_credito       enable row level security;
alter table public.seguimiento_efectivo  enable row level security;
alter table public.registros_pendientes  enable row level security;
alter table public.auditoria_cambios     enable row level security;
alter table public.rutina_nocturna_log   enable row level security;

-- 4) Functions + trigger ----------------------------------------------
create or replace function public.set_medio_pago()
returns trigger
language plpgsql
set search_path to 'public'
as $function$
begin
  select c.medio_pago into new.medio_pago from cuentas c where c.id_cuenta = new.id_cuenta;
  return new;
end;
$function$;

drop trigger if exists trg_set_medio_pago on public.seguimiento_efectivo;
create trigger trg_set_medio_pago
  before insert or update of id_cuenta on public.seguimiento_efectivo
  for each row execute function public.set_medio_pago();

create or replace function public.notificar_telegram(texto text)
returns bigint
language plpgsql
security definer
set search_path to ''
as $function$
declare
  token text;
  chat text;
begin
  select decrypted_secret into token from vault.decrypted_secrets where name = 'telegram_bot_token';
  select decrypted_secret into chat  from vault.decrypted_secrets where name = 'telegram_chat_id';
  if token is null or chat is null then
    raise exception 'Missing secrets telegram_bot_token / telegram_chat_id in Vault';
  end if;
  return net.http_post(
    url     := 'https://api.telegram.org/bot' || token || '/sendMessage',
    body    := jsonb_build_object('chat_id', chat, 'text', texto),
    headers := '{"Content-Type": "application/json"}'::jsonb
  );
end;
$function$;

-- Telegram sender is server-side only.
revoke all on function public.notificar_telegram(text) from public, anon, authenticated;
grant execute on function public.notificar_telegram(text) to postgres, service_role;

-- 5) Views (security_invoker: respect the caller's RLS) ----------------
create or replace view public.vista_saldos_cuentas with (security_invoker = on) as
 select c.id_cuenta, c.nombre_cuenta, c.naturaleza, c.estado,
        coalesce(sum(se.importe), 0) as saldo
   from cuentas c
   left join seguimiento_efectivo se on se.id_cuenta = c.id_cuenta
  where c.naturaleza <> 'credito'
  group by c.id_cuenta, c.nombre_cuenta, c.naturaleza, c.estado;

-- Credit cards: purchases are negative rows on the card account and a card
-- payment is a positive row on the same account (two linked rows, see
-- config/README.md), so debt = -sum(importe) per card. Works for N cards.
create or replace view public.vista_credito with (security_invoker = on) as
 select c.id_cuenta, c.nombre_cuenta, t.limite,
        coalesce(-sum(se.importe), 0) as deuda,
        t.limite - coalesce(-sum(se.importe), 0) as credito_disponible
   from cuentas c
   join tarjeta_credito t on t.id_cuenta = c.id_cuenta
   left join seguimiento_efectivo se on se.id_cuenta = c.id_cuenta
  group by c.id_cuenta, c.nombre_cuenta, t.limite;

-- Monthly budget for periods shorter than a year: base / meses_periodo
-- per month, compared with the current calendar month's spending.
create or replace view public.vista_presupuesto_mensual with (security_invoker = on) as
 with categoria_vigente as (
   select distinct on (codigo_categoria) id_categoria, codigo_categoria, nombre_categoria, tipo,
          periodicidad, meses_periodo, presupuesto_base
     from categorias
    where meses_periodo between 1 and 6
      and tipo not in ('traspaso','pago tarjeta')
      and fecha_inicio <= current_date and (fecha_fin is null or fecha_fin >= current_date)
    order by codigo_categoria, fecha_inicio desc
 ), consumo as (
   select c.codigo_categoria, sum(abs(se.importe)) as consumo_mes
     from seguimiento_efectivo se
     join categorias c on c.id_categoria = se.id_categoria
    where se.importe < 0 and date_trunc('month', se.fecha_operacion) = date_trunc('month', current_date::timestamptz)
    group by c.codigo_categoria
 )
 select cv.id_categoria, cv.codigo_categoria, cv.nombre_categoria, cv.tipo, cv.periodicidad,
        cv.presupuesto_base,
        round(cv.presupuesto_base / cv.meses_periodo, 2) as presupuesto_mes_proporcional,
        coalesce(co.consumo_mes, 0) as consumo_mes,
        round(cv.presupuesto_base / cv.meses_periodo, 2) - coalesce(co.consumo_mes, 0) as saldo_disponible
   from categoria_vigente cv
   left join consumo co on co.codigo_categoria = cv.codigo_categoria
  order by cv.nombre_categoria;

create or replace view public.vista_presupuesto_anual with (security_invoker = on) as
 with categoria_vigente as (
   select distinct on (codigo_categoria) id_categoria, codigo_categoria, nombre_categoria, tipo, periodicidad, presupuesto_base
     from categorias
    where periodicidad = 'anual'
      and fecha_inicio <= current_date and (fecha_fin is null or fecha_fin >= current_date)
    order by codigo_categoria, fecha_inicio desc
 ), consumo as (
   select c.codigo_categoria, sum(abs(se.importe)) as consumo_anio
     from seguimiento_efectivo se
     join categorias c on c.id_categoria = se.id_categoria
    where se.importe < 0 and date_trunc('year', se.fecha_operacion) = date_trunc('year', current_date::timestamptz)
    group by c.codigo_categoria
 )
 select cv.id_categoria, cv.codigo_categoria, cv.nombre_categoria, cv.tipo,
        cv.presupuesto_base as presupuesto_asignado,
        coalesce(co.consumo_anio, 0) as consumo_anio,
        cv.presupuesto_base - coalesce(co.consumo_anio, 0) as saldo_disponible
   from categoria_vigente cv
   left join consumo co on co.codigo_categoria = cv.codigo_categoria
  order by cv.nombre_categoria;

-- 6) Storage: private bucket for receipt photos, anon may only INSERT --
insert into storage.buckets (id, name, public)
values ('recibos', 'recibos', false)
on conflict (id) do nothing;

drop policy if exists recibos_anon_insert_only on storage.objects;
create policy recibos_anon_insert_only on storage.objects
  for insert to anon with check (bucket_id = 'recibos');

-- 7) Vault secrets (create by hand, values never live in this file) ----
--   select vault.create_secret('<bot token>', 'telegram_bot_token');
--   select vault.create_secret('<chat id>',   'telegram_chat_id');

-- 8) Nightly routine watermark: start auditing from the first operation ----
insert into public.rutina_nocturna_log (ultimo_id_auditado, resumen)
select 'SE000000', 'initial watermark'
where not exists (select 1 from public.rutina_nocturna_log);
