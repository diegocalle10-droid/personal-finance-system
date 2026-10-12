---
name: phase0-interview
description: Linear setup interview for the personal finance system. Asks for accounts, cards, categories (with periodicity and budget), labels and fixed expenses, then generates supabase/seed_usuario.sql, config/plantillas_estandarizadas.json and MIS_ATAJOS.md. Use when a new user sets the system up for the first time.
---

# Phase 0 — Setup interview

Run this once per user, in Claude Code, inside a private copy of the repo. Be linear: one block at a time, confirm the block, move on. Never invent data; if the user does not know, use the stated default. Everything is single currency (EUR) — do not ask about currencies or exchange rates.

## Outputs
1. `supabase/seed_usuario.sql` — accounts, cards, categories (use `supabase/seed_usuario.example.sql` as the exact shape).
2. `config/plantillas_estandarizadas.json` — start from `config/plantillas_estandarizadas.example.json`; replace placeholder ids with the real ones **after** the seed is applied (ask the user to run `select id_cuenta, nombre_cuenta from cuentas; select id_etiqueta, nombre_etiqueta from etiquetas;` and paste the result).
3. `MIS_ATAJOS.md` — for each of the 3 Shortcuts, which node to edit and with which value (account list, category list, fixed-expense menu, `{{GITHUB_OWNER}}`, `{{GITHUB_REPO}}`, `{{GITHUB_PAT}}`).
4. Repository variables to set in GitHub: `TZ_SISTEMA`, `CURRENCY_SYMBOL`.

## Questions (in order)

### 1. Basics
- Time zone (IANA, default `Europe/Madrid`) and currency symbol (default `€`).

### 2. Accounts — repeat until the user says "done"
- Name (unique), nature: `disponible` (spending/checking/cash), `ahorro` (savings), `credito` (credit card).
- Payment medium: `debito` or `credito` (credit only for credit cards).
- Opening balance and its date (generate an `ajuste patrimonial` row via the label `apertura` if not zero).

### 3. Credit cards — only for accounts with nature `credito`
- Credit limit in EUR. (Any number of cards is supported.)

### 4. Categories — start from the defaults in the example seed; edit, remove or add
For each category:
- `codigo_categoria` (slug), display name.
- `tipo`: `ingreso`, `gasto`, `coste fijo`, `traspaso`, `ajuste patrimonial`, `pago tarjeta`.
- `periodicidad`: `mensual`, `bimensual`, `trimestral`, `cuatrimestral`, `semestral`, `anual`, `puntual`. Explain: the budget is for ONE period, and the monthly view shows it divided by the months of the period (trimestral 90 → 30/month); `anual` shows in the yearly view; `puntual` has no periodic budget.
- `presupuesto_base` (EUR per period), `fecha_inicio`, whether it is currently active (if not, `fecha_fin`), optional `glosa` (e.g. the rent address, used as the comment of rent payments).
- Required for the system to work: one category of `tipo` `traspaso` (savings), one of `pago tarjeta` (if there are cards), one of `ajuste patrimonial`.

### 5. Labels
- Offer `supabase/seed_etiquetas_default.sql` (40 generic labels with criteria and Spanish keywords). Ask which to remove and which to add (name, criterion, keywords, `posibles_categorias`).
- Check every `posibles_categorias` code exists in step 4; otherwise warn.

### 6. Fixed expenses → templates
For each recurring operation: name, fixed or variable amount, account (fixed or chosen at runtime), category, label, comment (fixed text / category `glosa` / typed in the Shortcut). Credit card payment and savings deposit/withdrawal are always included from the example (two linked rows each).

## Finish
- Show a summary table per block and ask for a final confirmation.
- Write the three files and print the next steps: run `setup.sql` → `seed_etiquetas_default.sql` → `seed_usuario.sql`, resolve ids, finish templates, set GitHub secrets (`docs/SECRETS.md`), build the Shortcuts (`MIS_ATAJOS.md`).
- Never write secrets into any generated file.
