"""Publiczne demo: hala + scenariusz + stany (jak `demo_scenariusz` → `demo_dane --fill 0.7`), symulacja obu dni,
prezentacja 3D ze szablonu z publicznym linkiem (`core.demo`) i konto `demo` w roli Podgląd. Idempotentnie — ponowne uruchomienie niczego nie dubluje; `--reset` kasuje tylko obiekty demo
(halę i scenariusz po nazwie, import stanów demo) i siewa od nowa. Materiały demo są upsertem, więc zostają.
"""
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from core.demo import DEMO_USER, SHOWCASE_DAY, ensure_runs, ensure_showcase, mark_demo
from core.roles import GROUP_VIEWER
from masterdata.models import ImportLog
from masterdata.services import load_demo
from scenario.management.commands.demo_scenariusz import HALL, NAME
from scenario.models import Scenario
from twin.models import WarehouseModel

FILL = 0.7


def demo_stock_name():
    return f"Demo — stany ({HALL})"[:200]   # nazwa nadawana przez load_demo


class Command(BaseCommand):
    help = "Dane publicznego demo (hala, scenariusz, stany) i konto `demo` w roli Podgląd."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="usuń obiekty demo i utwórz je od nowa")

    @transaction.atomic
    def handle(self, *args, reset, **opts):
        if reset:
            ImportLog.objects.filter(kind="stock", name=demo_stock_name()).delete()
            WarehouseModel.objects.filter(name=HALL).delete()
            Scenario.objects.filter(name=NAME).delete()
        call_command("create_roles", stdout=self.stdout)
        call_command("demo_scenariusz", stdout=self.stdout)
        wm = WarehouseModel.objects.get(name=HALL)
        if not ImportLog.objects.filter(kind="stock", name=demo_stock_name()).exists():
            n_mat, log = load_demo(wm, fill=FILL)
            self.stdout.write(f"Materiały: {n_mat}, stany: {log.rows_ok} pozycji.")
        scenario = Scenario.objects.get(name=NAME)
        runs = ensure_runs(scenario, wm)
        sc = ensure_showcase(wm, runs.get(SHOWCASE_DAY))
        # R-02: rejestr danych demo — wszystko spoza niego blokuje wejście gościa (core.demo.exposure_reasons)
        mark_demo(wm, scenario, sc, *ImportLog.objects.filter(kind="stock", name=demo_stock_name()))
        self.stdout.write(f"Symulacja: {', '.join(sorted(runs))}; prezentacja „{sc.title}” ({len(sc.slides)} slajdów) "
                          f"pod /p/{sc.share_token}/ (stały adres: /demo/).")
        if not (settings.DEMO_PASSWORD or settings.DEMO_PUBLIC):
            self.stdout.write(self.style.WARNING("DEMO_PASSWORD puste i DEMO_PUBLIC wyłączone — konto `demo` pominięte."))
            return
        user, _ = User.objects.get_or_create(username=DEMO_USER)
        if settings.DEMO_PASSWORD:
            user.set_password(settings.DEMO_PASSWORD)
        else:
            user.set_unusable_password()          # tylko wejście gościa z /demo/, bez logowania hasłem
        user.is_staff = user.is_superuser = False
        user.save()
        user.groups.set([Group.objects.get(name=GROUP_VIEWER)])
        self.stdout.write(self.style.SUCCESS(f"Konto `{DEMO_USER}` (rola {GROUP_VIEWER}) gotowe."))
