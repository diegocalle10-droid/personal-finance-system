---
name: phase0-interview
description: Linear setup interview for the personal finance system. Asks for accounts, cards, categories (with periodicity and budget), labels and fixed expenses, then generates supabase/seed_usuario.sql, config/plantillas_estandarizadas.json and MIS_ATAJOS.md (node-by-node instructions for the three Shortcuts). Use when a new user sets the system up for the first time.
---

# Phase 0 — Setup interview

Run this once per user, in Claude Code, inside a private copy of the repo. Be linear: one block at a time, confirm the block, move on. Never invent data; if the user does not know, use the stated default. Everything is single currency (EUR) — do not ask about currencies or exchange rates. Never write secrets (tokens, keys) into any file: only tell the user where to paste them.

## Outputs
1. `supabase/seed_usuario.sql` — accounts, cards, categories (exact shape: `supabase/seed_usuario.example.sql`).
2. `config/plantillas_estandarizadas.json` — start from `config/plantillas_estandarizadas.example.json`. Ids (`CU…`, `ET…`) are known only after the seed runs: ask the user to run `select id_cuenta, nombre_cuenta from cuentas; select id_etiqueta, nombre_etiqueta from etiquetas;` and paste the result, then fill them in.
3. `MIS_ATAJOS.md` — see "MIS_ATAJOS.md format" below.
4. Repository variables to set in GitHub: `TZ_SISTEMA`, `CURRENCY_SYMBOL`.

## Questions (in order)

### 1. Basics
- Time zone (IANA, default `Europe/Madrid`) and currency symbol (default `€`).

### 2. Accounts — repeat until the user says "done"
- Name (unique, exact text; it will be typed in Shortcut lists), nature: `disponible` (spending/checking/cash), `ahorro` (savings), `credito` (credit card).
- Payment medium: `debito` or `credito` (credit only for credit cards).
- Opening balance and its date (generate an `ajuste patrimonial` row via the label `apertura` if not zero).
- Ask which account is **the savings account** (exactly one with nature `ahorro` is used by `savings_deposit` / `savings_withdrawal`).

### 3. Credit cards — only for accounts with nature `credito`
- Credit limit in EUR. (Any number of cards is supported.)

### 4. Categories — start from the defaults in the example seed; edit, remove or add
For each category:
- `codigo_categoria` (slug), display name.
- `tipo`: `ingreso`, `gasto`, `coste fijo`, `traspaso`, `ajuste patrimonial`, `pago tarjeta`.
- `periodicidad`: `mensual`, `bimensual`, `trimestral`, `cuatrimestral`, `semestral`, `anual`, `puntual`. Explain: the budget is for ONE period, and the monthly view shows it divided by the months of the period (trimestral 90 → 30/month); `anual` shows in the yearly view; `puntual` has no periodic budget.
- `presupuesto_base` (EUR per period), `fecha_inicio`, whether it is currently active (if not, `fecha_fin`), optional `glosa` (e.g. the rent address, used as the comment of the rent payment).
- Required by the system: `other_income` (type `ingreso`, used by the manual income flow), one `traspaso` (savings), one `pago tarjeta` (if there are cards), one `ajuste patrimonial`.

### 5. Labels
- Offer `supabase/seed_etiquetas_default.sql` (40 generic labels with criteria and Spanish keywords). Ask which to remove and which to add (name, criterion, keywords, `posibles_categorias`).
- Check every `posibles_categorias` code exists in step 4; otherwise warn.

### 6. Fixed expenses → templates and Gasto_fijo menu slots
Design rule (state it to the user): **a fixed expense has a fixed amount and a fixed paying account.** The Shortcut only sends *which* expense and *which date*; amount, account, category, label and comment come from the template. An expense whose amount changes does not belong here (it is logged with Manufinanza). A fixed *income* (e.g. salary) works the same way, with a positive amount.

For each fixed expense (the Shortcut has 7 slots; the user may use fewer or more):
1. **Menu label** — what the user wants to read in the menu (free text), e.g. `Rent`.
2. **Template key** — propose a `snake_case` slug from the label and confirm it; it must be unique and is case-sensitive, e.g. `rent`.
3. **Operation name** (`nombre_operacion`), e.g. `Rent payment`.
4. **Amount** (`importe_fijo`): negative for expenses, positive for income. Never zero or empty.
5. **Paying account**: pick from the accounts of block 2 → write its `id_cuenta` after the seed.
6. **Category** (`codigo_categoria`) from block 4 and **label** (`id_etiqueta`) from block 5 (suggest the best match by criterion).
7. **Comment**: fixed text (`comentario_fijo`), or `"comentario_fuente": "categorias.glosa"` to use the category's `glosa` (typical for rent).
8. **Valid from** (`fecha_inicio`).

Validation before writing: amount present and non-zero; account exists; category valid on `fecha_inicio`; key unique and does not collide with `savings_deposit`, `savings_withdrawal`, `credit_card_payment`.

Structural templates that are always included (do not ask, just confirm the accounts):
- `savings_deposit` / `savings_withdrawal`: the savings account is fixed in the template; the account lists in the Shortcut are the accounts the user moves money from/to.
- `credit_card_payment` (credit card payment, two linked rows): include **only if** the user has credit cards; it needs a payment option in the Shortcut (see the repo's `docs/SHORTCUTS.md`).

## MIS_ATAJOS.md format
Generate one section per Shortcut. For each node to edit give: **step number as the user sees it, node type, field, exact value to type**. Use tables, copy-paste-ready values, and no placeholder left unexplained. Required content:

**Common** — values of `GITHUB_OWNER`, `GITHUB_REPO`, `SUPABASE_PROJECT_REF` (ask the user for the three; they are not secrets) and, as a reminder only, where to paste `<GITHUB_PAT>` and `<SUPABASE_PUBLISHABLE_KEY>` (never write the values).
- Dispatch node URL: `https://api.github.com/repos/<owner>/<repo>/dispatches`, header `Authorization: Bearer <GITHUB_PAT>`.
- Upload node URL: `https://<ref>.supabase.co/storage/v1/object/` + variable `Text`; headers `apikey` and `Authorization: Bearer <SUPABASE_PUBLISHABLE_KEY>`.

**Gasto_fijo** — a table with one row per slot:

| Slot | Menu label | Text node (exact key) |
|---|---|---|
| 1 | `Rent` | `rent` |
| … | … | … |

plus: delete or duplicate slots to match the count, the two savings account lists (account names), and the dispatch nodes.

**Compras** — account list (names), category list (codes of spending categories the user wants offered), Wallet cards for the trigger, upload node, dispatch nodes.

**Manufinanza** — income account list, income category code, expense account list (incl. credit cards), expense category list, upload node, dispatch nodes.

## Finish
- Show a summary table per block and ask for a final confirmation.
- Write the three files and print the next steps: run `setup.sql` → `seed_etiquetas_default.sql` → `seed_usuario.sql`, resolve ids, finish templates, set GitHub secrets (`docs/SECRETS.md`), build the Shortcuts from `MIS_ATAJOS.md` and `docs/SHORTCUTS.md`.
- Never write secrets into any generated file.
