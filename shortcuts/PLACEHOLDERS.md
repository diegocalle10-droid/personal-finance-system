# Placeholders in the shortcut JSON files

Every `{{UPPER_CASE}}` token below is a value **you** provide when you build (or publish) your own copy of the Shortcuts. Lower-case / mixed-case tokens such as `{{Selected Item}}` or `{{Ask for Input}}` are normal Shortcuts magic variables and are left as they are.

`python tools/list_placeholders.py` prints where each one is used.

## Secrets — fill only in your private Shortcut, never in anything you share

| Placeholder | What it is | Where to get it | Used in |
|---|---|---|---|
| `{{GITHUB_PAT}}` | fine-grained GitHub token, this repo only, *Contents: Read and write* | GitHub → Settings → Developer settings → Fine-grained tokens | every HTTP request to `api.github.com` (all 3 Shortcuts) |
| `{{SUPABASE_PUBLISHABLE_KEY}}` | publishable (anon) key; the bucket policy only lets it INSERT | Supabase → Project Settings → API Keys | photo upload step (Manufinanza, Compras) |

## Your infrastructure — identifies your copy

| Placeholder | What it is | Example shape |
|---|---|---|
| `{{GITHUB_OWNER}}` | GitHub user or org that owns your private repo | `your-user` |
| `{{GITHUB_REPO}}` | name of your private repo | `my-finance` |
| `{{SUPABASE_PROJECT_REF}}` | project reference (the subdomain of your Supabase URL) | `abcdefghijklmnopqrst` |

## Your data — lists the Phase 0 interview generates for you

| Placeholder | What to put | Must match |
|---|---|---|
| `{{ACCOUNT_1}}`, `{{ACCOUNT_2}}`, … | names of your non-credit accounts, exactly as in `cuentas.nombre_cuenta` (add or remove list items as needed) | `cuentas.nombre_cuenta` |
| `{{CREDIT_CARD_1}}`, … | names of your credit-card accounts | `cuentas.nombre_cuenta` |
| `{{CATEGORY_1}}` … `{{CATEGORY_15}}` | the **codes** (`codigo_categoria`) of the spending categories you want in the menu (any number) | `categorias.codigo_categoria` |
| `{{INCOME_CATEGORY_CODE}}` | code of your catch-all income category (default `ingresos_varios`) | `categorias.codigo_categoria`, type `ingreso` |
| `{{TUS_TARJETAS_WALLET}}` | the Wallet cards that trigger the `Compras` automation (picked in the Shortcuts app, not text) | — |

## Values that are fixed text, not placeholders, but must stay consistent
- `Gasto_fijo` sends a `tipo_ingesta` text per menu option (`subscription_example`, `phone_example`, `rent`, `transit_pass`, `pago_tarjeta`, `ahorro_aporte`, `ahorro_retiro`). Each one must be a key of your `config/plantillas_estandarizadas.json`. The menu labels you see (Subscription, Rent, …) are free text.
- Event types are fixed by the workflows: `gasto_dinamico`, `gasto_foto`, `ingesta_estandarizada`.
- The photo path is always `recibos/<random>.jpg` (bucket `recibos`).

## Making a shareable copy
1. Duplicate the Shortcut in the Shortcuts app.
2. Empty every field in the table above (leave the lists empty and the token/URL fields blank).
3. Share → Copy iCloud Link, and put the link in the release notes.
The receiver fills the blanks using the `MIS_ATAJOS.md` the Phase 0 interview generated for them.
