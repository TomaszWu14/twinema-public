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


def demo_showcase():
    """Prezentacja demo z aktywnym linkiem albo None (demo nie zasiane / link wyłączony)."""
    return (Showcase.objects.filter(title=SHOWCASE, share_token__isnull=False, share_expires__gt=timezone.now())
            .only("pk", "title", "share_token").order_by("-pk").first())
