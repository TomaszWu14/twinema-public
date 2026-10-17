"""Zadanie kolejki: symulacja scenariusza na modelu hali (US-007)."""

from django.contrib.auth import get_user_model

from scenario import services
from scenario.models import Scenario
from twin.models import WarehouseModel


def simulate_scenario(p):
    sc = Scenario.objects.get(pk=p["scenario"])
    wm = WarehouseModel.objects.get(pk=p["model"])
    user = get_user_model().objects.filter(pk=p.get("user")).first()
    sc.ensure_days(with_defaults=False)
    done = []
    for day in sc.days.filter(kind__in=p["kinds"]).prefetch_related("inbound", "outbound"):
        run = services.simulate(day, wm, runs=p["runs"], user=user)
        n_err = sum(b["severity"] == "error" for b in run.result["bottlenecks"])
        done.append(f"{day.get_kind_display().lower()}: {len(run.result['bottlenecks'])} wąskich gardeł"
                    f"{f' ({n_err} krytycznych)' if n_err else ''}, {run.duration_s:g} s")
    return {"summary": f"Symulacja na „{wm}” ({p['runs']} przebiegów) — " + "; ".join(done) + "."}
