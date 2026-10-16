import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core import jobs
from core.roles import any_role, designer
from twin.models_tasks import WarehouseTaskBatch

from . import services
from .models import ModelRun


def _int(raw, default, lo, hi):
    try:
        return min(hi, max(lo, int(raw)))
    except (TypeError, ValueError):
        return default


@any_role
def home(request):
    return render(request, "ml/home.html", {
        "batches": WarehouseTaskBatch.objects.filter(status="done"),
        "streams": services.STREAM_LABELS.items(),
        "runs": ModelRun.objects.select_related("batch", "created_by")[:30],
        "job": jobs.latest("ml.run", user=request.user.pk),
    })


@designer
@require_POST
def run(request, kind):
    batch = get_object_or_404(WarehouseTaskBatch, pk=request.POST.get("batch") or 0, status="done")
    params = {"kind": kind, "batch": batch.pk, "user": request.user.pk}
    if kind == "forecast":
        stream = request.POST.get("stream", "total")
        params.update(stream=stream if stream in services.STREAM_LABELS else "total",
                      years=_int(request.POST.get("years"), 5, 1, 20))
    elif kind == "segmentation":
        params.update(k=_int(request.POST.get("k"), 4, 2, 8))
    else:
        return redirect("ml:home")
    jobs.enqueue("ml.run", params, user=request.user)             # T-1: model liczy worker kolejki
    messages.success(request, "Model liczy się w tle — wynik pojawi się na tej stronie.")
    return redirect("ml:home")


@any_role
def detail(request, pk):
    mr = get_object_or_404(ModelRun.objects.select_related("batch"), pk=pk)
    ctx = {"run": mr, "res": mr.result}
    if mr.kind == "forecast" and mr.result.get("ok"):
        r = mr.result
        ctx["chart"] = {k: r[k] for k in ("labels", "actual", "fitted", "forecast", "lower", "upper")}
        ctx["stream_label"] = services.STREAM_LABELS.get(mr.params.get("stream"), "")
        ctx["sim_links"] = {s: "?" + urlencode({"p": 95, "mult": r[f"mult_{s}"]}) for s in ("p50", "p90")}
    return render(request, f"ml/{mr.kind}.html", ctx)


@designer
def segments_csv(request, pk):
    mr = get_object_or_404(ModelRun, pk=pk, kind="segmentation")
    names = {s["id"]: s["name"] for s in mr.result.get("segments", [])}
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="twinema_segmenty_{mr.pk}.csv"'
    resp.write("﻿")
    w = csv.writer(resp, delimiter=";")
    w.writerow(["materiał", "segment", "nazwa segmentu"])
    for m, sid in sorted(mr.result.get("assignment", {}).items()):
        w.writerow([m if not m[:1] in "=+-@" else "'" + m, sid, names.get(sid, "")])
    return resp
