"""Kopie zapasowe bazy i mediów (US-009, R-10; decyzja PO Z-36: RPO 24 h, RTO 4 h, retencja 14 kopii).

Jeden zestaw = katalog `RRRRMMDD-GGMMSS/` w BACKUP_DIR: zrzut bazy, archiwum mediów i `manifest.json`
(czas, wersja aplikacji, rozmiary, SHA-256). Katalog kopii musi leżeć poza wolumenem mediów — najlepiej
na osobnym, szyfrowanym magazynie (RUNBOOK).
"""

import hashlib
import json
import os
import shutil
import sqlite3
# subprocess: tylko pg_dump ze stałą listą argumentów, bez powłoki
import subprocess  # nosec B404
import tarfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connections

KEEP = 14
# katalogi plików tymczasowych (podglądy importów) — nie są danymi do odtworzenia
SKIP_MEDIA = {"ewm_tasks", "masterdata_uploads"}


class BackupError(Exception):
    pass


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dump_database(target_dir):
    """Zrzut bazy `default`: PostgreSQL → pg_dump (format custom), SQLite → kopia przez API backup."""
    db = settings.DATABASES["default"]
    if db["ENGINE"].endswith("sqlite3"):
        out = target_dir / "baza.sqlite3"
        src = sqlite3.connect(str(db["NAME"]))
        try:
            dst = sqlite3.connect(str(out))
            with dst:
                src.backup(dst)
            dst.close()
        finally:
            src.close()
        return out
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise BackupError("Brak programu pg_dump w obrazie (pakiet postgresql-client).")
    out = target_dir / "baza.dump"
    env = {**os.environ, "PGPASSWORD": db.get("PASSWORD", "")}       # hasło w zmiennej, nie w argumentach
    if db.get("OPTIONS", {}).get("sslmode"):
        env["PGSSLMODE"] = db["OPTIONS"]["sslmode"]
    cmd = [pg_dump, "--format=custom", "--no-owner", f"--file={out}", f"--host={db.get('HOST') or 'localhost'}",
           f"--port={db.get('PORT') or '5432'}", f"--username={db.get('USER', '')}", db["NAME"]]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600, check=False)  # nosec B603
    if result.returncode != 0:
        raise BackupError(f"pg_dump zakończył się kodem {result.returncode}: {result.stderr.strip()[:300]}")
    return out


def archive_media(target_dir):
    out = target_dir / "media.tar.gz"
    root = Path(settings.MEDIA_ROOT)
    with tarfile.open(out, "w:gz") as tar:
        if root.exists():
            for item in sorted(root.iterdir()):
                if item.name not in SKIP_MEDIA:
                    tar.add(item, arcname=item.name)
    return out


def prune(backup_dir, keep=KEEP):
    """Zostawia `keep` najnowszych zestawów (nazwy katalogów sortują się chronologicznie)."""
    sets = sorted(p for p in backup_dir.iterdir() if p.is_dir() and (p / "manifest.json").exists())
    removed = sets[:-keep] if keep else sets
    for p in removed:
        shutil.rmtree(p)
    return [p.name for p in removed]


def make_backup(backup_dir=None, now=None, keep=KEEP):
    backup_dir = Path(backup_dir or settings.BACKUP_DIR or "")
    if not str(backup_dir) or str(backup_dir) == ".":
        raise BackupError("Ustaw BACKUP_DIR — katalog kopii poza wolumenem mediów.")
    if Path(settings.MEDIA_ROOT).resolve() in backup_dir.resolve().parents or \
            backup_dir.resolve() == Path(settings.MEDIA_ROOT).resolve():
        raise BackupError("BACKUP_DIR nie może leżeć w katalogu mediów (kopia pakowałaby samą siebie).")
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    target = backup_dir / stamp
    target.mkdir(parents=True, exist_ok=False)
    try:
        connections["default"].close()               # zrzut z czystego połączenia
        files = [dump_database(target), archive_media(target)]
        manifest = {"created": stamp, "version": getattr(settings, "GIT_SHA", "") or "unknown",
                    "database": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1],
                    "files": {f.name: {"bytes": f.stat().st_size, "sha256": _sha256(f)} for f in files}}
        (target / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    except Exception:
        shutil.rmtree(target, ignore_errors=True)    # niepełny zestaw nie udaje kopii
        raise
    return target, manifest, prune(backup_dir, keep)


def verify(set_dir):
    """Sprawdza sumy SHA-256 zestawu względem manifestu → lista problemów (pusta = zgodny)."""
    set_dir = Path(set_dir)
    manifest = json.loads((set_dir / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for name, meta in manifest["files"].items():
        path = set_dir / name
        if not path.exists():
            problems.append(f"brak pliku {name}")
        elif _sha256(path) != meta["sha256"]:
            problems.append(f"suma SHA-256 się nie zgadza: {name}")
    return problems
