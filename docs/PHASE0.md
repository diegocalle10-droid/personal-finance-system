# Phase 0 — what the interview asks and what it produces

Run it once, in Claude Code, inside your private copy of the repo. It follows `phase0/SKILL.md`; this page is the user-facing summary.

## Before you start
Have at hand: your accounts and cards (names, which are credit cards, credit limits), your monthly budget per spending area, your recurring payments (rent, subscriptions, phone, transport pass), and the day you want to start tracking.

## The six blocks
| # | Block | You answer | Becomes |
|---|---|---|---|
| 1 | Basics | time zone, currency symbol | GitHub variables `TZ_SISTEMA`, `CURRENCY_SYMBOL` |
| 2 | Accounts | name, nature (`disponible` / `ahorro` / `credito`), debit or credit, opening balance | rows in `cuentas` |
| 3 | Credit cards | credit limit per card | rows in `tarjeta_credito` |
| 4 | Categories | code, name, type, **period** (`mensual`, `bimensual`, `trimestral`, `cuatrimestral`, `semestral`, `anual`, `puntual`), budget per period, start date, active or not, note | rows in `categorias` |
| 5 | Labels | keep / remove / add labels from the default taxonomy and link them to categories | `etiquetas` |
| 6 | Fixed expenses | name, fixed or variable amount, account, category, label, comment | `config/plantillas_estandarizadas.json` and the fixed-expense Shortcut menu |

## Budget periods in one line
The budget you enter is for **one period**. The monthly view shows it divided by the months of the period (trimestral 90 → 30 per month, semestral 600 → 100 per month). `anual` categories appear in the yearly view; `puntual` ones have no periodic budget.

## Outputs
- `supabase/seed_usuario.sql` — run after `setup.sql` and `seed_etiquetas_default.sql`.
- `config/plantillas_estandarizadas.json` — your fixed-expense templates (placeholders replaced with real ids after the seed).
- `MIS_ATAJOS.md` — for each Shortcut: which node to edit and with which value (account list, category list, fixed-expense menu).

## Re-running
Categories are versioned: to change a budget later, close the old row (`fecha_fin`) and insert a new one with the same code. The interview can be re-run for additions; it never overwrites existing rows.
