# Setup guide

Estimated time: 60-90 minutes the first time.

1. **Private copy of the repo.** Create a private repo from this one (use "Use this template" or copy the files). In it, remove `config/plantillas_estandarizadas.json` and `supabase/seed_usuario.sql` from `.gitignore`.
2. **Supabase project.** Create a project (any region). In the SQL Editor run, in order:
   1. `supabase/setup.sql` (schema, views, trigger, bucket; safe to re-run)
   2. `supabase/seed_etiquetas_default.sql` (optional default labels)
3. **Phase 0 interview.** Open the repo in Claude Code and run the interview in `phase0/SKILL.md`. It produces `supabase/seed_usuario.sql`, `config/plantillas_estandarizadas.json` and `MIS_ATAJOS.md`. Run the seed in the SQL Editor, then replace the placeholder ids in the templates with the real ones (the skill tells you how).
4. **Telegram.** Create a bot with @BotFather, get your chat id, create the two Vault secrets ([SECRETS.md](SECRETS.md)).
5. **GitHub secrets and variables** ([SECRETS.md](SECRETS.md)).
6. **Shortcuts.** Build/duplicate them following `shortcuts/README.md` and `MIS_ATAJOS.md`.
7. **Smoke test.** From the Shortcut (or `gh api repos/<owner>/<repo>/dispatches -f event_type=ingesta_estandarizada -F client_payload[tipo_ingesta]=...`) send one expense, check the Actions run, the Telegram message and the row in `seguimiento_efectivo`.
8. **Nightly routine.** Create a scheduled Claude routine with the Supabase MCP connector and paste `rutina_nocturna/RUNBOOK.md` (replace `<SUPABASE_PROJECT_REF>` and `<TZ_SISTEMA>`). Run it at a time before the purge workflow (02:30 UTC) — e.g. 01:00 UTC.

## Useful views
- `vista_saldos_cuentas`: balance per non-credit account.
- `vista_credito`: debt and available credit per card.
- `vista_presupuesto_mensual`: budget vs this month's spending (periods up to semestral, divided by months).
- `vista_presupuesto_anual`: annual categories vs this year's spending.

## Troubleshooting
- Failed ingestion → a Telegram ❌ message and a `registros_pendientes` row; the nightly routine resolves it.
- "No account named ..." → the Shortcut sent a name that is not in `cuentas.nombre_cuenta` (must match exactly).
- "No valid version of category ..." → no `categorias` row valid on that date for that code.
