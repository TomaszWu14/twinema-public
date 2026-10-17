"""US-009: kopie zapasowe bazy i mediów — zestaw z manifestem, retencja, sprawdzenie sum, PostgreSQL bez hasła w argumentach."""
import json
import sqlite3
import tarfile
import tempfile
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core import backup


def _tmp():
    return Path(tempfile.mkdtemp(prefix="twinema-backup-"))


class BackupTests(SimpleTestCase):
    def setUp(self):
        self.root = _tmp()
        self.media = self.root / "media"
        (self.media / "renders").mkdir(parents=True)
        (self.media / "renders" / "a.png").write_bytes(b"png")
        (self.media / "ewm_tasks").mkdir()
        (self.media / "ewm_tasks" / "podglad.csv").write_text("tymczasowy")
        self.db = self.root / "db.sqlite3"
        con = sqlite3.connect(self.db)
        con.execute("create table t (x)")
        con.execute("insert into t values (42)")
        con.commit()
        con.close()
        self.dest = self.root / "kopie"
        sqlite_db = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": self.db}}
        self.settings_cm = override_settings(MEDIA_ROOT=str(self.media), BACKUP_DIR=str(self.dest), DATABASES=sqlite_db)
        self.settings_cm.enable()
        self.addCleanup(self.settings_cm.disable)

    def test_backup_set_restores_database_and_media(self):
        target, manifest, removed = backup.make_backup(now=datetime(2026, 10, 16, 2, 0))
        self.assertEqual(target.name, "20261016-020000")
        self.assertEqual(set(manifest["files"]), {"baza.sqlite3", "media.tar.gz"})
        self.assertEqual(removed, [])
        con = sqlite3.connect(target / "baza.sqlite3")
        self.assertEqual(con.execute("select x from t").fetchone(), (42,))
        con.close()
        with tarfile.open(target / "media.tar.gz") as tar:
            names = tar.getnames()
        self.assertIn("renders/a.png", names)
        self.assertFalse(any(n.startswith("ewm_tasks") for n in names))       # pliki tymczasowe pominięte
        self.assertEqual(backup.verify(target), [])

    def test_verify_detects_tampering(self):
        target, _, _ = backup.make_backup()
        (target / "media.tar.gz").write_bytes(b"zmienione")
        self.assertEqual(backup.verify(target), ["suma SHA-256 się nie zgadza: media.tar.gz"])
        with self.assertRaises(CommandError):
            call_command("backup", "--verify", str(target), stdout=StringIO())

    def test_keeps_only_newest_sets(self):
        for day in range(1, 5):
            backup.make_backup(now=datetime(2026, 10, day, 2, 0), keep=2)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["20261003-020000", "20261004-020000"])

    def test_failed_backup_leaves_no_partial_set(self):
        with mock.patch.object(backup, "archive_media", side_effect=OSError("brak miejsca")), \
                self.assertRaises(OSError):
            backup.make_backup()
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_refuses_without_dir_or_inside_media(self):
        with override_settings(BACKUP_DIR=""), self.assertRaises(backup.BackupError):
            backup.make_backup()
        with override_settings(BACKUP_DIR=str(self.media / "kopie")), self.assertRaises(backup.BackupError):
            backup.make_backup()

    def test_keep_must_be_at_least_one(self):
        """Przegląd kodu (G): `--keep 0` nie kasuje wszystkich kopii, w tym właśnie utworzonej."""
        backup.make_backup(now=datetime(2026, 10, 1, 2, 0))
        for keep in (0, -1):
            with self.assertRaises(CommandError):
                call_command("backup", "--keep", str(keep), stdout=StringIO())
        self.assertEqual([p.name for p in self.dest.iterdir()], ["20261001-020000"])

    def test_command_reports_set(self):
        out = StringIO()
        call_command("backup", stdout=out)
        self.assertIn("baza.sqlite3", out.getvalue())

    def test_postgres_password_not_in_arguments(self):
        pg = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "twinema", "USER": "app",
                          "PASSWORD": "tajne-haslo", "HOST": "db", "PORT": "5432", "OPTIONS": {"sslmode": "require"}}}

        def fake_run(cmd, env, **kw):
            Path(next(a for a in cmd if a.startswith("--file=")).split("=", 1)[1]).write_bytes(b"dump")
            return mock.Mock(returncode=0, stderr="")

        with override_settings(DATABASES=pg), mock.patch.object(backup.shutil, "which", return_value="/usr/bin/pg_dump"), \
                mock.patch.object(backup.subprocess, "run", side_effect=fake_run) as run:
            target, manifest, _ = backup.make_backup()
        cmd, env = run.call_args.args[0], run.call_args.kwargs["env"]
        self.assertNotIn("tajne-haslo", " ".join(cmd))
        self.assertEqual((env["PGPASSWORD"], env["PGSSLMODE"]), ("tajne-haslo", "require"))
        self.assertIn("baza.dump", manifest["files"])
        self.assertEqual(json.loads((target / "manifest.json").read_text())["database"], "postgresql")

    def test_postgres_error_is_reported(self):
        pg = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "x", "OPTIONS": {}}}
        with override_settings(DATABASES=pg), mock.patch.object(backup.shutil, "which", return_value="/usr/bin/pg_dump"), \
                mock.patch.object(backup.subprocess, "run", return_value=mock.Mock(returncode=1, stderr="brak dostępu")), \
                self.assertRaisesRegex(backup.BackupError, "brak dostępu"):
            backup.make_backup()
