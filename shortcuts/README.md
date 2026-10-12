# iOS Shortcuts

Three Shortcuts feed the system. `source/*.shortcut` holds the importable (unsigned) files, the `*.json` files next to this one are the same sequence in readable form. The exported structure (human-readable JSON, secrets and personal lists replaced by placeholders) lives next to this file: `Manufinanza.json` (manual hub: income / expense, with or without receipt photo), `Compras.json` (Wallet/NFC trigger, same flows) and `Gasto_fijo.json` (fixed expenses, savings, card payment). They are documentation of the exact action sequence; they were produced with `tools/shortcut_to_json.py` from the real `.shortcut` files. A duplicable iCloud copy (with empty fields) is linked from the release notes.

Full list of placeholders, what each one is and where to get it: [PLACEHOLDERS.md](PLACEHOLDERS.md). In short: `{{GITHUB_OWNER}}`, `{{GITHUB_REPO}}`, `{{GITHUB_PAT}}`, `{{SUPABASE_PROJECT_REF}}`, `{{SUPABASE_PUBLISHABLE_KEY}}`, `{{ACCOUNT_n}}`, `{{CREDIT_CARD_n}}`, `{{CATEGORY_n}}`, `{{TUS_TARJETAS_WALLET}}`.

All of them end with an HTTP `POST` to `https://api.github.com/repos/{{GITHUB_OWNER}}/{{GITHUB_REPO}}/dispatches` with header `Authorization: Bearer {{GITHUB_PAT}}` and a JSON body `{"event_type": "...", "client_payload": {...}}`.

| Shortcut | `event_type` | `client_payload` |
|---|---|---|
| Dynamic expense (NFC / manual) | `gasto_dinamico` | `cuenta` (account name), `fecha` (optional, `YYYY-MM-DD`), `lineas`: array of `{importe, categoria, nombre_operacion, comentario}` (1-3) |
| Receipt photo | `gasto_foto` | `cuenta`, `foto_bucket_path` (object uploaded to bucket `recibos`), `categorias` (codes preselected in the Shortcut) |
| Fixed expenses | `ingesta_estandarizada` | `tipo_ingesta` (template key) and `fecha` only: amount and account are fixed in the template. Savings add `monto`, `cuenta`, `comentario`; card payments add `monto`, `cuenta`, `cuenta_destino` |

Static lists inside the Shortcuts (accounts, categories, fixed-expense menu) are generated for you by the Phase 0 interview in `MIS_ATAJOS.md`: it tells you which node to edit and with which value.

Payment of a credit card: `tipo_ingesta = credit_card_payment`, `cuenta` = paying account, `cuenta_destino` = the card.
