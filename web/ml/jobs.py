"""Zadanie kolejki: przebieg modelu ML (T-1) — prognoza wolumenów albo segmentacja SKU."""

from django.contrib.auth import get_user_model

from twin.models_tasks import WarehouseTaskBatch

from . import services


def run_model(p):
    batch = WarehouseTaskBatch.objects.get(pk=p["batch"], status="done")
    user = get_user_model().objects.filter(pk=p.get("user")).first()
    if p["kind"] == "forecast":
        mr = services.run_forecast(batch, p["stream"], p["years"], user)
    else:
        mr = services.run_segmentation(batch, p["k"], user)
    return {"run": mr.pk, "ok": bool(mr.result.get("ok")), "reason": mr.result.get("reason", "")}
