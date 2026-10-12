# -*- coding: utf-8 -*-
"""
Daily purge of already processed registros_pendientes.

The nightly Claude routine cannot delete rows: the Supabase MCP connector asks
for human approval on any destructive SQL and the routine is unattended. So
the routine only MARKS each pending it resolves (estado='procesado') and this
job, which uses the service key over REST and does not go through MCP,
physically deletes them once a day.

It runs 1 h 30 min after the routine (both crons in UTC, no daylight saving
shift). Pendings in estado 'pendiente' are never touched.
"""
import sys

import requests

from motor_supabase import SUPABASE_URL, REST_HEADERS, notificar_telegram


def purgar_procesados():
    """Deletes pendings with estado='procesado'. Returns the deleted rows."""
    url = f"{SUPABASE_URL}/rest/v1/registros_pendientes"
    r = requests.delete(url, headers=REST_HEADERS, params={"estado": "eq.procesado"}, timeout=15)
    r.raise_for_status()
    return r.json()


def main():
    try:
        borrados = purgar_procesados()
    except requests.RequestException as e:
        notificar_telegram(f"❌ Daily purge of processed pendings failed: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not borrados:
        print("Nothing to purge.")
        return

    ids = ", ".join(fila["id_pendiente"] for fila in borrados)
    notificar_telegram(f"🧹 Daily purge: {len(borrados)} processed pending(s) removed: {ids}")
    print(f"Purged: {ids}")


if __name__ == "__main__":
    main()
