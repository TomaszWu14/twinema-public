"""Zadanie kolejki: import pliku danych podstawowych (T-1). Plik czeka w MEDIA_ROOT/masterdata_uploads/."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model

from . import importers, services


def upload_dir():
    path = Path(settings.MEDIA_ROOT) / "masterdata_uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def import_upload(p):
    path = upload_dir() / Path(p["file"]).name                 # tylko nazwa — bez wyjścia poza katalog
    user = get_user_model().objects.filter(pk=p.get("user")).first()
    try:
        if not path.exists():
            return {"error": "Plik importu wygasł albo nie istnieje — wgraj go ponownie."}
        try:
            log = services.import_file(p["kind"], p["name"], path.read_bytes(), user)
        except importers.ImportFileError as exc:
            return {"error": str(exc)}
        return {"log": log.pk, "rows_ok": log.rows_ok, "rows_total": log.rows_total, "rows_rejected": log.rows_rejected}
    finally:
        path.unlink(missing_ok=True)
