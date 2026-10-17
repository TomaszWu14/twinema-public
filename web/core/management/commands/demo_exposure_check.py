"""US-011: ostrzeżenie przy starcie, gdy demo publiczne działa na instancji z danymi spoza demo (R-02).
Nie blokuje startu; wejście gościa jest wtedy wyłączone (decyzja PO) — komunikat trafia do logów kontenera."""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.demo import exposure_reasons


class Command(BaseCommand):
    help = "Ostrzega, gdy DEMO_PUBLIC jest włączone, a w bazie są dane spoza demo."

    def handle(self, *args, **opts):
        if not settings.DEMO_PUBLIC:
            return
        reasons = exposure_reasons()
        if reasons:
            self.stderr.write(self.style.WARNING(
                "UWAGA: DEMO_PUBLIC=true, a w bazie są dane spoza demo (" + ", ".join(reasons) + "). "
                "Wejście gościa jest wyłączone. Demo publiczne uruchamiaj na osobnej instancji "
                "albo ustaw DEMO_PUBLIC=false (docs/operacje/RUNBOOK.md)."))
