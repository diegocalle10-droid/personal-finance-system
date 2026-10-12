# Label glossary (reference)

The glossary lives in Supabase: table `etiquetas`, columns `keyword` (product
examples), `criterio` (one sentence that defines the label and tells it apart
from its siblings, e.g. groceries = "to eat at home" vs cafe = "served in a
bar") and `posibles_categorias`. It is the single source of truth: the scripts
read it live on every ingestion, with no cache. This file is documentation
only; no script reads it.

## How each ingestion uses it

- **Dynamic expense (no photo):** deterministic keyword matching bounded to the
  category chosen in the Shortcut. No match → `registros_pendientes`.
- **Photo expense:** the prompt is built in `scripts/ingesta_foto.py` with a
  numbered MENU of category / label pairs, limited to the categories that come
  from the Shortcut, with their criterion and the keywords as examples. The
  model picks one number per product. If the keywords recognize the product
  (first in the literal receipt text, then in the name the model wrote), the
  glossary overrides the model's choice. Amounts are verified against the
  receipt TOTAL.

## How to teach a new product

Add the item (not the whole phrase: "parodontax", not "I bought parodontax at
Carrefour") to the `keyword` array of its label in Supabase. It applies from the
next ingestion, with no deployment. The nightly routine does this for you.

The default keywords are **Spanish** because they match Spanish-language
receipts. Add keywords in the language of your own receipts.

```sql
SELECT nombre_etiqueta, posibles_categorias, keyword
FROM etiquetas WHERE estado = 'activa' ORDER BY nombre_etiqueta;
```

## Principles

- Every line is classified by what the product IS, not by the store.
- Discounts and promotions are netted into the line of the product they apply to.
- Categories are fixed by the user in the Shortcut (budget); the ingestion only
  splits products among those categories.
