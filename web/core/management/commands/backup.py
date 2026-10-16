"""US-009: kopia bazy i mediów do BACKUP_DIR (`manage.py backup`), sprawdzenie zestawu (`--verify KATALOG`).
Harmonogram: codziennie z zadania zaplanowanego platformy (RUNBOOK, decyzja PO Z-36)."""

from django.core.management.base import BaseCommand, CommandError

from core import backup


class Command(BaseCommand):
    help = "Kopia zapasowa bazy i mediów (US-009) albo sprawdzenie sum kontrolnych zestawu."

    def add_arguments(self, parser):
        parser.add_argument("--verify", metavar="KATALOG", help="sprawdź sumy SHA-256 istniejącego zestawu")
        parser.add_argument("--keep", type=int, default=backup.KEEP, help="ile najnowszych zestawów zostawić")

    def handle(self, *args, **options):
        if options["verify"]:
            problems = backup.verify(options["verify"])
            if problems:
                raise CommandError("Zestaw niezgodny: " + "; ".join(problems))
            self.stdout.write(self.style.SUCCESS("Zestaw zgodny z manifestem."))
            return
        try:
            target, manifest, removed = backup.make_backup(keep=options["keep"])
        except backup.BackupError as exc:
            raise CommandError(str(exc)) from exc
        sizes = ", ".join(f"{n}: {m['bytes'] // 1024} KB" for n, m in manifest["files"].items())
        self.stdout.write(self.style.SUCCESS(f"Kopia {target} ({sizes})."
                                             + (f" Usunięto starsze: {', '.join(removed)}." if removed else "")))
