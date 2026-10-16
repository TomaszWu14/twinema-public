"""Prezentacje 3D (P1): lista, tworzenie (ze szablonem startowym), odtwarzacz + edytor slajdów, dane JSON.

Podgląd ogląda (odtwarzacz i dane: layout 3D + wyniki, bez danych źródłowych), Projektant tworzy i edytuje.
Udostępnienie: adres dla zalogowanych albo (P3) publiczny link tylko do odczytu — losowy token w adresie,
wygasa po N dniach, Projektant może go wyłączyć; zakres danych jak dla roli Podgląd."""
import json
import secrets
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import any_role, designer
from twin.views.warehouse_model import model_scene_data
from twin.layout import rack_row
from twin.models import WarehouseModel
from twin.shared import safe_json
from twin.site import site_kpi

from .models import ScenarioRun, Showcase
from .showcase import CARDS, SlideError, clean_slides, kpi_cards, template_slides
from .views_play import bottleneck_focus, layout_places, peak_index
from .views_sim import _sim_view
from core import audit
from core.models import AuditEvent

MAX_BODY = 512 * 1024
SHARE_DAYS = (1, 7, 14, 30, 90)


class ShowcaseForm(forms.ModelForm):
    class Meta:
        model = Showcase
        fields = ["title", "model", "run"]
        widgets = {"title": forms.TextInput(attrs={"class": "form-control", "maxlength": 200}),
                   "model": forms.Select(attrs={"class": "form-control"}),
                   "run": forms.Select(attrs={"class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["run"].queryset = ScenarioRun.objects.defer("events").select_related("scenario", "model")
        self.fields["run"].required = False
        self.fields["run"].empty_label = "— bez wyników symulacji —"

    def clean(self):
        d = super().clean()
        if d.get("run") and d.get("model") and d["run"].model_id != d["model"].pk:
            raise forms.ValidationError("Wynik symulacji musi dotyczyć wybranego modelu hali.")
        return d


def _context(sc):
    """Wszystko, czego potrzebuje odtwarzacz i szablon startowy (jedno źródło)."""
    wm = sc.model
    racks, features, _ = model_scene_data(wm)
    floor = {"width": wm.floor_width_m, "depth": wm.floor_depth_m}
    places = layout_places(features, floor)
    site = site_kpi(wm.site, {**floor, "clear_height": wm.clear_height_m},
                    [rack_row(r) for r in wm.racks.all()]) if wm.site else None
    run, view, bns, peak = sc.run, None, [], 0
    if run:
        view = _sim_view(run)
        bns = [{**b, **bottleneck_focus(b, places)} for b in run.result.get("bottlenecks", [])]
        peak = peak_index(run.result.get("rep", {}).get("timeline") or {"t": []}) * 900
    cards = kpi_cards(view["groups"] if view else (), view and view["capacity"], site, view and view["costs"])
    return {"wm": wm, "racks": racks, "features": features, "floor": floor, "places": places, "site_kpi": site,
            "run": run, "view": view, "bottlenecks": bns, "peak": peak, "cards": cards}


def _template(sc, ctx):
    run, agg = ctx["run"], (ctx["run"].result.get("agg", {}) if ctx["run"] else {})
    cap, site = (ctx["view"] or {}).get("capacity") or {}, ctx["site_kpi"] or {}
    mean = lambda k: agg[k]["mean"] if k in agg else None             # noqa: E731
    facts = {"positions": cap.get("positions"), "need": cap.get("need"), "fill_pct": cap.get("fill_pct"),
             "day": {"typical": "typowym", "peak": "szczytowym"}.get(run.day_kind) if run else None,
             "pallets_in": mean("pallets_in"), "pallets_out": mean("pallets_out"), "parcels": mean("parcels"),
             "bottlenecks": len(ctx["bottlenecks"]) if run else None,
             "errors": sum(b["severity"] == "error" for b in ctx["bottlenecks"]),
             "coverage_pct": site.get("coverage_pct"), "reserve_m2": site.get("reserve_m2")}
    return template_slides(
        title=sc.title, floor=ctx["floor"], racks=ctx["racks"], places=ctx["places"], site_kpi_=ctx["site_kpi"],
        cards=ctx["cards"], facts=facts,
        run={"day": run.get_day_kind_display().lower(), "has_events": run.has_events, "peak_t": ctx["peak"],
             "bottlenecks": ctx["bottlenecks"]} if run else None)


@any_role
def showcase_list(request):
    raw = request.GET.get("run", "")
    run = ScenarioRun.objects.defer("events", "result").filter(pk=int(raw)).select_related("scenario").first() if raw.isdigit() else None
    form = ShowcaseForm(initial={
        "model": run.model_id if run else WarehouseModel.objects.values_list("pk", flat=True).first(),
        "run": run.pk if run else None, "title": f"{run.scenario.name} — prezentacja" if run else ""})
    return render(request, "scenario/showcase_list.html", {
        "form": form, "items": Showcase.objects.select_related("model", "run", "created_by").defer("run__events", "run__result")[:60]})


@designer
@require_POST
def showcase_create(request):
    form = ShowcaseForm(request.POST)
    if not form.is_valid():
        for errs in form.errors.values():
            messages.error(request, " ".join(errs))
        return redirect("scenario:showcase_list")
    sc = form.save(commit=False)
    sc.created_by = request.user
    sc.save()
    sc.slides = _template(sc, _context(sc))
    sc.save(update_fields=["slides"])
    messages.success(request, f"Utworzono prezentację „{sc}” — {len(sc.slides)} slajdów ze szablonu. "
                              "Popraw podpisy, dodaj własne ujęcia i zapisz.")
    return redirect("scenario:showcase", pk=sc.pk)


def _detail(request, sc, public=False):
    ctx = _context(sc)
    if public:
        urls = {"data": reverse("scenario:public_data", args=[sc.share_token]), "save": None,
                "events": reverse("scenario:public_events", args=[sc.share_token]) if sc.run_id else None}
    else:
        urls = {"data": reverse("scenario:showcase_data", args=[sc.pk]),
                "save": reverse("scenario:showcase_save", args=[sc.pk]),
                "events": reverse("scenario:run_events", args=[sc.run_id]) if sc.run_id else None}
    active = bool(sc.share_token and sc.share_expires and sc.share_expires > timezone.now())
    resp = render(request, "scenario/showcase.html", {
        "sc": sc, "cards": ctx["cards"], "card_names": CARDS, "bottlenecks": ctx["bottlenecks"], "public": public,
        **({"is_designer": False, "is_admin": False} if public else {}),   # link publiczny = zawsze sam pokaz
        "share_url": request.build_absolute_uri(reverse("scenario:showcase", args=[sc.pk])),
        "public_url": request.build_absolute_uri(reverse("scenario:public", args=[sc.share_token])) if active else "",
        "share_days": SHARE_DAYS, "config_json": safe_json(urls),
    })
    return _no_index(resp) if public else resp


def _no_index(resp):
    """Publiczny link: bez indeksowania, bez wysyłania adresu z tokenem dalej, bez cache pośredników."""
    resp["X-Robots-Tag"] = "noindex, nofollow"
    resp["Referrer-Policy"] = "no-referrer"
    resp["Cache-Control"] = "private, no-store"
    return resp


def _data(sc):
    ctx = _context(sc)
    tl = (sc.run.result.get("rep", {}).get("timeline") if sc.run else None) or {"t": []}
    return JsonResponse({
        "format": "twinema.showcase", "version": 1, "title": sc.title, "slides": sc.slides,
        "floor": ctx["floor"], "racks": ctx["racks"], "features": ctx["features"], "site": sc.model.site or {},
        "places": ctx["places"], "cards": ctx["cards"], "bottlenecks": ctx["bottlenecks"], "peak_t": ctx["peak"],
        "has_events": bool(sc.run and sc.run.has_events),
        "timeline": {"step_s": 900, "fleet_busy": tl.get("fleet_busy", []),
                     "people": {p: v["busy"] for p, v in (tl.get("people") or {}).items()}},
    }, json_dumps_params={"ensure_ascii": False})


def _shared(token):
    """Prezentacja po aktywnym tokenie; nieznany, wyłączony albo wygasły → 404 (bez rozróżniania)."""
    sc = Showcase.objects.select_related("model", "run__scenario").defer("run__events").filter(
        share_token=token, share_expires__gt=timezone.now()).first() if token else None
    if not sc:
        raise Http404
    return sc


@any_role
def showcase_detail(request, pk):
    return _detail(request, get_object_or_404(
        Showcase.objects.select_related("model", "run__scenario").defer("run__events"), pk=pk))


@any_role
def showcase_data(request, pk):
    """Dane odtwarzacza: scena (layout + działka), miejsca, wyniki (karty KPI, wąskie gardła, oś czasu), slajdy."""
    return _data(get_object_or_404(Showcase.objects.select_related("model", "run").defer("run__events"), pk=pk))


def public_showcase(request, token):
    return _detail(request, _shared(token), public=True)


def public_data(request, token):
    return _no_index(_data(_shared(token)))


def public_events(request, token):
    sc = _shared(token)
    if not sc.run_id:
        raise Http404
    run = ScenarioRun.objects.only("pk", "model_id", "day_kind", "result", "events").get(pk=sc.run_id)
    return _no_index(JsonResponse({"format": "twinema.scenario-events", "version": 1, "run": run.pk,
                                   "model": run.model_id, "day": run.day_kind, "seed": run.result["rep"]["seed"],
                                   "columns": ["t_s", "obj", "kind", "what", "place"], "events": run.events}))


@designer
@require_POST
def showcase_share(request, pk):
    sc = get_object_or_404(Showcase, pk=pk)
    try:
        days = int(request.POST.get("days", 14))
    except ValueError:
        days = 0
    if days not in SHARE_DAYS:
        messages.error(request, f"Ważność linku: {', '.join(map(str, SHARE_DAYS))} dni.")
        return redirect("scenario:showcase", pk=pk)
    sc.share_token, sc.share_expires = secrets.token_urlsafe(24), timezone.now() + timedelta(days=days)
    sc.save(update_fields=["share_token", "share_expires", "updated_at"])
    audit.record(request, AuditEvent.LINK_CREATE, sc, object_type="prezentacja 3D", label=sc.title,
                 detail=f"ważny {days} dni")
    messages.success(request, f"Utworzono publiczny link ważny {days} dni — poprzedni link (jeśli był) przestał działać.")
    return redirect("scenario:showcase", pk=pk)


@designer
@require_POST
def showcase_unshare(request, pk):
    sc = get_object_or_404(Showcase, pk=pk)
    if sc.share_token:
        audit.record(request, AuditEvent.LINK_REVOKE, sc, object_type="prezentacja 3D", label=sc.title)
    Showcase.objects.filter(pk=pk).update(share_token=None, share_expires=None)
    messages.success(request, "Publiczny link wyłączony.")
    return redirect("scenario:showcase", pk=pk)


@designer
@require_POST
def showcase_save(request, pk):
    sc = get_object_or_404(Showcase, pk=pk)
    if len(request.body) > MAX_BODY:
        return JsonResponse({"error": "Za dużo danych (maks. 512 KB)."}, status=413)
    try:
        data = json.loads(request.body)
        slides = clean_slides(data.get("slides") if isinstance(data, dict) else None)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "To nie jest poprawny JSON."}, status=400)
    except SlideError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    sc.slides = slides
    sc.save(update_fields=["slides", "updated_at"])
    return JsonResponse({"ok": True, "slides": slides})


@designer
@require_POST
def showcase_reset(request, pk):
    sc = get_object_or_404(Showcase.objects.select_related("model", "run").defer("run__events"), pk=pk)
    sc.slides = _template(sc, _context(sc))
    sc.save(update_fields=["slides", "updated_at"])
    messages.success(request, "Slajdy zastąpione szablonem startowym.")
    return redirect("scenario:showcase", pk=pk)


@designer
@require_POST
def showcase_delete(request, pk):
    sc = get_object_or_404(Showcase, pk=pk)
    title = sc.title
    audit.record(request, AuditEvent.DELETE, sc, object_type="prezentacja 3D", label=title)
    sc.delete()
    messages.success(request, f"Usunięto prezentację „{title}”.")
    return redirect("scenario:showcase_list")
