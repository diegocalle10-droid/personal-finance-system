# -*- coding: utf-8 -*-
"""
Cleanup of the 'recibos' bucket: runs every 2 days (cron) and deletes only
objects older than RETENCION_DIAS. A 7-day window gives the nightly Claude
routine (it runs every night) plenty of time to process a photo pending
before the photo is lost.

Double condition before deleting: besides the age, any photo still referenced
by an unprocessed pending (origen gasto_foto, estado='pendiente') is excluded
- if it is still there, the system still needs it no matter how many days have
passed. Photos of already processed pendings expire normally.
"""
from datetime import datetime, timedelta, timezone

from motor_supabase import (
    listar_objetos_storage,
    borrar_objetos_storage,
    listar_fotos_pendientes_de_borrado,
    notificar_telegram,
)

BUCKET = "recibos"
RETENCION_DIAS = 7


def nombre_en_bucket(ruta):
    """Pending records store the path as the Shortcut built it
    ("recibos/123.jpg", bucket included) while Storage lists the object name
    without the bucket ("123.jpg"). Both are normalized to the object name."""
    prefijo = BUCKET + "/"
    return ruta[len(prefijo):] if ruta.startswith(prefijo) else ruta


def main():
    objetos = listar_objetos_storage(BUCKET)
    limite = datetime.now(timezone.utc) - timedelta(days=RETENCION_DIAS)
    referenciadas = {nombre_en_bucket(r) for r in listar_fotos_pendientes_de_borrado()}

    a_borrar = [
        obj["name"] for obj in objetos
        if obj.get("created_at")
        and datetime.fromisoformat(obj["created_at"].replace("Z", "+00:00")) < limite
        and obj["name"] not in referenciadas
    ]

    if not a_borrar:
        print("Nothing to delete.")
        return

    resultado = borrar_objetos_storage(BUCKET, a_borrar)
    if not resultado.ok:
        notificar_telegram(f"⚠️ Receipt cleanup failed ({resultado.status_code}): {resultado.text}")
        print(f"ERROR: {resultado.status_code} {resultado.text}")
        return

    print(f"OK: {len(a_borrar)} object(s) deleted: {', '.join(a_borrar)}")


if __name__ == "__main__":
    main()
