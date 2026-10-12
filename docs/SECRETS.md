# Secrets and variables

Nothing sensitive lives in the code. Every value below is created by you and stored only in the place indicated.

## GitHub → Settings → Secrets and variables → Actions

**Secrets**

| Name | Where to get it | Used by |
|---|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL | all scripts |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API Keys → **secret key** (`sb_secret_...`) or the legacy `service_role` JWT. Both work. Never put it in a Shortcut. | all scripts |
| `TELEGRAM_BOT_TOKEN` | @BotFather → `/newbot` | all scripts |
| `TELEGRAM_CHAT_ID` | send a message to your bot, open `https://api.telegram.org/bot<token>/getUpdates` | all scripts |
| `DASHSCOPE_API_KEY` | Alibaba Model Studio (DashScope) → API keys | photo flow |
| `QWEN_BASE_URL` | DashScope compatible-mode base URL of your workspace | photo flow |

**Variables** (optional)

| Name | Default |
|---|---|
| `TZ_SISTEMA` | `Europe/Madrid` |
| `CURRENCY_SYMBOL` | `€` |

## Supabase Vault (used by `notificar_telegram`)
```sql
select vault.create_secret('<bot token>', 'telegram_bot_token');
select vault.create_secret('<chat id>',   'telegram_chat_id');
```

## In the iOS Shortcuts (stored inside the Shortcut, never in the repo)
- **GitHub fine-grained token** limited to this single repository with *Contents: Read and write* (required by `repository_dispatch`). Set an expiry.
- **Supabase publishable (anon) key**: only needed by the photo Shortcut to upload to the `recibos` bucket; storage policy `recibos_anon_insert_only` allows INSERT only, so the key cannot read or list anything.

## Rotation
Rotate the service role key and the GitHub token if a Shortcut is ever shared by mistake. The shared JSON exports in `shortcuts/` use placeholders (`{{GITHUB_PAT}}`, ...) and must stay that way.
