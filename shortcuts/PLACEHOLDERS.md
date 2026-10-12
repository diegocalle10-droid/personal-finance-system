# Placeholders in the shortcut JSON files

Every `{{UPPER_CASE}}` token below is a value **you** provide when you build (or publish) your own copy of the Shortcuts. Lower-case / mixed-case tokens such as `{{Selected Item}}` or `{{Ask for Input}}` are normal Shortcuts magic variables and are left as they are. In the real Shortcut files the same blanks appear as `completar` / `complete`.

`python tools/list_placeholders.py` prints where each one is used. The node-by-node guide with diagrams is [docs/SHORTCUTS.md](../docs/SHORTCUTS.md).

## Secrets — fill only in your private Shortcut, never in anything you share

| Placeholder | What it is | Where to get it | Used in |
|---|---|---|---|
| `{{GITHUB_PAT}}` | fine-grained GitHub token, this repo only, *Contents: Read and write* | GitHub → Settings → Developer settings → Fine-grained tokens | `Authorization: Bearer …` of every GitHub HTTP node (all 3 Shortcuts) |
| `{{SUPABASE_PUBLISHABLE_KEY}}` | publishable (anon) key; the bucket policy only lets it INSERT | Supabase → Project Settings → API Keys | `apikey` and `Authorization: Bearer …` of the photo upload node (Manufinanza, Compras) |

## Your infrastructure — identifies your copy

| Placeholder | What it is | Example shape |
|---|---|---|
| `{{GITHUB_OWNER}}` | GitHub user or org that owns your private repo | `your-user` |
| `{{GITHUB_REPO}}` | name of your private repo | `my-finance` |
| `{{SUPABASE_PROJECT_REF}}` | project reference (the subdomain of your Supabase URL) | `abcdefghijklmnopqrst` |

## Fixed expenses (Gasto_fijo) — one pair per slot

| Placeholder | What to put | Must match |
|---|---|---|
| `{{FIXED_EXPENSE_n_LABEL}}` | the text you want to see in the menu (free text) | — |
| `{{FIXED_EXPENSE_n_KEY}}` | the **exact** template key sent as `tipo_ingesta` (case-sensitive, `snake_case`) | a top-level key of `config/plantillas_estandarizadas.json` |

Rule: a fixed expense has a fixed amount and a fixed account (both in the template), so the Shortcut sends only the key and the date. Add slots by duplicating one, remove the ones you do not need. `ahorro_aporte` and `ahorro_retiro` are structural and stay as they are.

## Your data — lists the Phase 0 interview generates for you

| Placeholder | What to put | Must match |
|---|---|---|
| `{{ACCOUNT_1}}`, `{{ACCOUNT_2}}`, … | names of your accounts, exactly as in `cuentas.nombre_cuenta` (add or remove list items as needed; credit cards go in the lists where you can pay with them) | `cuentas.nombre_cuenta` |
| `{{CATEGORY_1}}`, `{{CATEGORY_2}}`, … | the **codes** (`codigo_categoria`) of the spending categories you want in the menu (any number) | `categorias.codigo_categoria` |
| `{{INCOME_CATEGORY_CODE}}` | code of your catch-all income category (default `ingresos_varios`) | `categorias.codigo_categoria`, type `ingreso` |
| `{{TUS_TARJETAS_WALLET}}` | the Wallet cards that trigger the `Compras` automation (picked in the Shortcuts app, not text) | — |

## Values that are fixed text, not placeholders
- Event types are fixed by the workflows: `gasto_dinamico`, `gasto_foto`, `ingesta_estandarizada`.
- The photo path is always `recibos/<random>.jpg` (bucket `recibos`).
- Savings keys: `ahorro_aporte`, `ahorro_retiro`.

## Making a shareable copy
1. Duplicate the Shortcut in the Shortcuts app.
2. Empty every field in the tables above (leave lists empty, token/URL fields blank or `completar`).
3. Share → Copy iCloud Link, and put the link in the release notes and in `docs/SHORTCUTS.md`.
The receiver fills the blanks using the `MIS_ATAJOS.md` the Phase 0 interview generated for them.
