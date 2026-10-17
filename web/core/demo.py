"""Publiczne demo: symulacja obu dni scenariusza demo na hali demo, prezentacja 3D ze szablonu (szczyt dnia)
i jej publiczny link bez wygasania w praktyce. Wywołuje `seed_demo`; `/demo/` czyta `demo_showcase()`.
"""
import secrets
from datetime import timedelta

from django.utils import timezone

from scenario import services
from scenario.models import ScenarioRun, Showcase

DEMO_USER = "demo"                     # konto Podglądu publicznego demo (seed_demo, wejście gościa)
SHOWCASE = "Centrum dystrybucyjne — pokaz demo"
SHOWCASE_DAY = "peak"                  # szczyt: wąskie gardła z podpowiedziami — ciekawszy pokaz niż dzień typowy
RUNS = 12
SHARE_DAYS = 3650                      # link demo ma działać „zawsze”; każdy seed_demo przesuwa ważność


def ensure_runs(scenario, wm):
    """Po jednym wyniku symulacji na dzień scenariusza (istniejący zostaje) → {rodzaj dnia: ScenarioRun}."""
    scenario.ensure_days(with_defaults=False)
    runs = {}
    for day in scenario.days.prefetch_related("inbound", "outbound"):
        runs[day.kind] = (ScenarioRun.objects.defer("events").filter(scenario=scenario, model=wm, day_kind=day.kind)
                          .order_by("-pk").first() or services.simulate(day, wm, runs=RUNS))
    return runs


def ensure_showcase(wm, run):
    """Prezentacja demo ze szablonu startowego + publiczny link; token zostaje, ważność się odnawia."""
    from scenario.views_showcase import _context, _template

    sc = Showcase.objects.filter(title=SHOWCASE, model=wm).first()
    if sc is None:
        sc = Showcase.objects.create(title=SHOWCASE, model=wm, run=run)
        sc.slides = _template(sc, _context(sc))
    sc.share_token = sc.share_token or secrets.token_urlsafe(24)
    sc.share_expires = timezone.now() + timedelta(days=SHARE_DAYS)
    sc.save()
    return sc


def mark_demo(*objs):
    """Zapisuje obiekty jako dane demo (wywołuje `seed_demo`); idempotentnie."""
    from django.contrib.contenttypes.models import ContentType

    from .models import DemoObject
    for obj in objs:
        DemoObject.objects.get_or_create(content_type=ContentType.objects.get_for_model(obj), object_id=str(obj.pk))


def demo_pks(model):
    """Klucze obiektów danego modelu zapisanych w rejestrze demo."""
    from django.contrib.contenttypes.models import ContentType

    from .models import DemoObject
    ids = DemoObject.objects.filter(content_type=ContentType.objects.get_for_model(model))
    return [int(i) for i in ids.values_list("object_id", flat=True)]


def demo_showcase():
    """Prezentacja demo (z rejestru `seed_demo`, nie po tytule) z aktywnym linkiem albo None."""
    return (Showcase.objects.filter(pk__in=demo_pks(Showcase), share_token__isnull=False,
                                    share_expires__gt=timezone.now())
            .only("pk", "title", "share_token").order_by("-pk").first())


def exposure_reasons():
    """US-011 (SEC, R-02): dane spoza demo na instancji — powody (puste = tylko dane demo).

    Demo publiczne wpuszcza każdego jako Podgląd, więc na instancji z prawdziwymi danymi je ujawnia.
    Dane demo to obiekty z rejestru `seed_demo` (`mark_demo`) — nazwa pliku czy obiektu niczego nie przesądza.
    Prezentacje, filmy, rendery i wyniki symulacji należą do hali, więc wystarczy sprawdzić hale i scenariusze."""
    from equipment.models import Equipment
    from masterdata.models import ImportLog
    from scenario.models import Scenario
    from twin.models import WarehouseLocationMasterBatch, WarehouseModel
    from twin.models_tasks import WarehouseTaskBatch

    reasons = []
    if WarehouseTaskBatch.objects.exists():
        reasons.append("importy zadań magazynowych")
    if WarehouseLocationMasterBatch.objects.exists():
        reasons.append("master lokalizacji")
    if ImportLog.objects.exclude(pk__in=demo_pks(ImportLog)).exists():
        reasons.append("importy danych spoza demo")
    if WarehouseModel.objects.exclude(pk__in=demo_pks(WarehouseModel)).exists():
        reasons.append("hale spoza demo")
    if Scenario.objects.exclude(pk__in=demo_pks(Scenario)).exists():
        reasons.append("scenariusze spoza demo")
    if Equipment.objects.exclude(created_by=None).exists():
        reasons.append("własne modele sprzętu")
    return reasons

