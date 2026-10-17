"""Worker kolejki zadań w bazie (US-007, US-024): `manage.py run_jobs` (pętla) albo `--once`."""

import signal

from django.core.management.base import BaseCommand

from core import jobs


class Command(BaseCommand):
    help = "Wykonuje zadania z kolejki w bazie (symulacje, kalibracje, importy)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="wykonaj zaległe zadania i zakończ")
        parser.add_argument("--poll", type=float, default=2.0, help="sekundy między sprawdzeniami kolejki")

    def handle(self, *args, **options):
        if options["once"]:
            self.stdout.write(f"Wykonano zadań: {jobs.run_pending()}.")
            return
        stopping = []
        signal.signal(signal.SIGTERM, lambda *_: stopping.append(True))
        self.stdout.write("Worker kolejki zadań uruchomiony.")
        jobs.worker_loop(poll_s=options["poll"], stop=lambda: bool(stopping))
