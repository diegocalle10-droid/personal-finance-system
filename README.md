# Personal Finance System (iOS Shortcuts + Supabase + GitHub Actions + Claude)

Frictionless expense tracking: tap an NFC tag or a Shortcut on your iPhone, the expense lands in a Postgres ledger, gets labeled automatically, and a nightly Claude routine audits and improves the labeling. Single currency (EUR), budgets with flexible periods, receipt photos read by a vision model.

> **Resumen en español:** sistema de finanzas personales sin fricción. Un atajo de iPhone (NFC o manual) envía el gasto a GitHub Actions, que lo valida y lo guarda en Supabase; las etiquetas se resuelven por palabras clave y, si algo falla, queda como pendiente que una rutina nocturna de Claude resuelve y audita. Una entrevista inicial ("Fase 0") genera tus cuentas, categorías y plantillas. Ver [docs/SETUP.md](docs/SETUP.md).

## How it works

```
iOS Shortcut ──repository_dispatch──▶ GitHub Actions ──REST──▶ Supabase (Postgres + Storage)
   (NFC / manual / photo)                 │ scripts/*.py             │
                                          ├─ Telegram notification   ├─ views: balances, credit, budgets
                                          └─ on failure ─▶ registros_pendientes
                                                                     ▲
                       Nightly Claude routine (MCP) ─ resolves pendings, audits labels, grows keywords
```

| Flow | Script | Trigger |
|---|---|---|
| Dynamic expense (1-3 lines) | `scripts/ingesta_dinamica.py` | `gasto_dinamico` |
| Receipt photo (vision model) | `scripts/ingesta_foto.py` | `gasto_foto` |
| Fixed expenses / savings / card payment | `scripts/ingesta_estandarizada.py` | `ingesta_estandarizada` |
| Receipt cleanup (7 days) | `scripts/limpieza_recibos.py` | cron |
| Purge processed pendings | `scripts/purgar_pendientes_procesados.py` | cron |

## Design highlights
- **Versioned categories (SCD2):** change a budget by closing a row and inserting a new one; history keeps resolving with the budget valid at each date.
- **Budget periods:** `mensual`, `bimensual`, `trimestral`, `cuatrimestral`, `semestral`, `anual`, `puntual`; the monthly view divides the period budget by its months.
- **Deterministic labeling first, AI second:** keyword matching bounded by the chosen category; the vision model only picks a number from a closed menu and amounts are verified against the receipt TOTAL.
- **Nothing is lost:** any failure becomes a pending record resolved overnight; nightly routine is idempotent and never deletes.
- **Credit cards:** a payment is two linked rows (paying account −, card +), so any number of cards works and debt is a simple per-card sum.
- **Secrets never in code:** GitHub Secrets and Supabase Vault only.

## What you need
| Piece | Why | Cost |
|---|---|---|
| iPhone with Shortcuts | capture (NFC / Wallet trigger / manual) | — |
| GitHub account (private copy of this repo) | runs the ingestion workflows | free tier |
| Supabase project | Postgres ledger + private bucket for receipt photos | free tier |
| Telegram bot | notifications | free |
| DashScope (Qwen) API key | only for receipt photos | pay-per-use, cents |
| Claude (Claude Code + routines) | Phase 0 interview and nightly routine | your plan |

## Quick start
1. Create a Supabase project; run `supabase/setup.sql`, then `supabase/seed_etiquetas_default.sql`.
2. Run the **Phase 0 interview** ([phase0/SKILL.md](phase0/SKILL.md)) with Claude Code: it generates `supabase/seed_usuario.sql`, your templates and `MIS_ATAJOS.md`.
3. Set secrets and variables — which key to create, where, and where it is used: [docs/SECRETS.md](docs/SECRETS.md). What the interview asks: [docs/PHASE0.md](docs/PHASE0.md).
4. Build the Shortcuts ([shortcuts/README.md](shortcuts/README.md)).
5. Schedule the nightly routine ([rutina_nocturna/RUNBOOK.md](rutina_nocturna/RUNBOOK.md)).

In your private copy, remove `config/plantillas_estandarizadas.json` and `supabase/seed_usuario.sql` from `.gitignore` so the workflows can read your templates.

## Tests
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

## License
MIT
