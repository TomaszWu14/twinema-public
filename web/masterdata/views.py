import uuid
from pathlib import Path

from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.roles import any_role, designer

from .jobs import upload_dir
from . import importers, services
from . import packaging
from .models import SPECIAL_FLAGS, Carrier, ImportLog, Material, PalletClass
from core import audit, jobs
from core.models import AuditEvent

MAX_UPLOAD_MB = 25
UPLOAD_SUFFIXES = (".csv", ".txt", ".xlsx", ".xlsm")
KINDS = dict(ImportLog.KIND_CHOICES)
KIND_HELP = {
    "materials": "Kod, nazwa, grupa, sztuka → karton → paleta (wymiary, wagi, przeliczniki, warstwy), nośnik, klasy, "
                 "ABC, strefy specjalne. Istniejące kody są aktualizowane tylko w kolumnach z pliku.",
    "locations": "Kody lokalizacji z typem, poziomem i wymiarami. Każdy import tworzy nowy aktywny master.",
    "stock": "Lokalizacja, materiał, ilość, HU, partia, data ważności. Najnowszy import = aktualny stan w scenie 3D.",
}


def _counts(field):
    """[(etykieta, liczba materiałów)] — zbiorcze liczby, które widzi też rola Podgląd."""
    return [(row[field] or "bez klasy", row["n"]) for row in
            Material.objects.values(field).annotate(n=Count("pk")).order_by(field)]


@any_role
def home(request):
    from twin.models import WarehouseLocationMasterBatch, WarehouseModel

    stock_log = services.current_stock_log()
    return render(request, "masterdata/home.html", {
        "kinds": [(k, label, KIND_HELP[k]) for k, label in ImportLog.KIND_CHOICES],
        "n_materials": Material.objects.count(),
        "n_groups": Material.objects.exclude(group="").values("group").distinct().count(),
        "stock_log": stock_log,
        "stock_locations": stock_log.stock_items.values("location_code").distinct().count() if stock_log else 0,
        "master": WarehouseLocationMasterBatch.objects.filter(is_active=True).first(),
        "by_height": _counts("height_class__label"), "by_weight": _counts("weight_class__label"),
        "by_flag": [(label, Material.objects.filter(**{f: True}).count()) for f, label in SPECIAL_FLAGS],
        "logs": ImportLog.objects.select_related("uploaded_by")[:20],
        "models": WarehouseModel.objects.order_by("-created_at")[:20],
        "max_mb": MAX_UPLOAD_MB,
        "job": jobs.latest("masterdata.import", user=request.user.pk),
    })


@designer
@require_POST
def upload(request, kind):
    if kind not in KINDS:
        return redirect("masterdata:home")
    f = request.FILES.get("file")
    if not f:
        messages.error(request, "Wybierz plik do importu.")
        return redirect("masterdata:home")
    if f.size > MAX_UPLOAD_MB * 1024 * 1024:
        messages.error(request, f"Plik jest większy niż {MAX_UPLOAD_MB} MB — podziel go.")
        return redirect("masterdata:home")
    suffix = Path(f.name).suffix.lower()
    if suffix not in UPLOAD_SUFFIXES:
        messages.error(request, f"{KINDS[kind]}: obsługiwane pliki to CSV i XLSX.")
        return redirect("masterdata:home")
    # T-1: import liczy worker kolejki — duży plik nie przekracza limitu żądania
    stored = upload_dir() / f"{uuid.uuid4().hex}{suffix}"
    with open(stored, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    jobs.enqueue("masterdata.import", {"kind": kind, "name": f.name[:200], "file": stored.name,
                                       "user": request.user.pk}, user=request.user)
    audit.record(request, AuditEvent.IMPORT, object_type=f"import: {KINDS[kind]}", label=f.name[:200],
                 detail=f"plik {f.size // 1024} KB, zlecony do kolejki")
    messages.success(request, f"{KINDS[kind]}: import trwa w tle — raport pojawi się na tej stronie.")
    return redirect("masterdata:home")


@designer                      # raport pokazuje wiersze danych źródłowych — nie dla roli Podgląd
def log_detail(request, pk):
    log = get_object_or_404(ImportLog, pk=pk)
    labels = importers.LABELS
    return render(request, "masterdata/log_detail.html", {
        "log": log,
        "columns": [(labels.get(f, f), header) for f, header in log.columns.items()],
        "unmapped": [labels[f] for f in importers.ALIASES[log.kind] if f not in log.columns],
        "stock_preview": log.stock_items.all()[:50] if log.kind == "stock" else None,
    })


@any_role
def template(request, kind):
    if kind not in KINDS:
        return redirect("masterdata:home")
    resp = HttpResponse("﻿" + importers.template_csv(kind), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="twinema_wzor_{kind}.csv"'
    return resp


@designer                      # lista materiałów = dane źródłowe (decyzja #25: Podgląd ich nie widzi)
def materials(request):
    g = request.GET
    q = (g.get("q") or "").strip()
    qs = Material.objects.select_related("carrier", "height_class", "weight_class")
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(group__icontains=q))
    for key in ("height_class", "weight_class"):
        if g.get(key, "").isdigit():
            qs = qs.filter(**{f"{key}_id": int(g[key])})
    if g.get("abc") in ("A", "B", "C"):
        qs = qs.filter(abc_manual=g["abc"])
    flag = g.get("flaga")
    if flag in dict(SPECIAL_FLAGS):
        qs = qs.filter(**{flag: True})
    page = Paginator(qs, 50).get_page(g.get("page"))
    history = services.abc_from_history()
    for m in page.object_list:
        m.abc_history = history.get(m.code, "")
        m.cpp = packaging.cartons_per_pallet(m.as_dict())
    groups = Material.objects.exclude(group="").values("group").annotate(n=Count("pk")).order_by("-n")[:12]
    query = g.copy()
    query.pop("page", None)
    return render(request, "masterdata/materials.html", {
        "page": page, "q": q, "groups": groups, "query": query.urlencode(), "f": g,
        "heights": PalletClass.objects.filter(kind="height"), "weights": PalletClass.objects.filter(kind="weight"),
        "flags": SPECIAL_FLAGS, "has_history": bool(history)})


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        exclude = ["code"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            if not isinstance(f.widget, forms.CheckboxInput):
                f.widget.attrs.setdefault("class", "form-control")
        self.fields["carrier"].empty_label = "domyślny (EUR)"
        self.fields["height_class"].empty_label = self.fields["weight_class"].empty_label = "dobierz z palety"


@designer
def material_edit(request, pk):
    m = get_object_or_404(Material, pk=pk)
    form = MaterialForm(request.POST or None, instance=m)
    if request.method == "POST" and form.is_valid():
        m = form.save(commit=False)
        services.classify_materials([m])
        m.save()
        messages.success(request, f"Zapisano materiał {m.code}.")
        return redirect("masterdata:material_edit", pk=m.pk)
    carrier = (m.carrier or Carrier.objects.filter(is_default=True).first())
    cd = carrier.as_dict() if carrier else None
    d = m.as_dict()
    return render(request, "masterdata/material_form.html", {
        "m": m, "form": form, "carrier": carrier, "warnings": packaging.warnings(d, cd),
        "calc": {"cpp": packaging.cartons_per_pallet(d), "height": packaging.pallet_height_cm(d, cd),
                 "weight": packaging.pallet_weight_kg(d, cd)},
        "abc_history": services.abc_from_history().get(m.code, ""),
    })


CarrierFormSet = forms.modelformset_factory(
    Carrier, fields=["name", "length_cm", "width_cm", "height_cm", "weight_kg", "max_load_h_cm", "max_load_kg",
                     "is_default"], extra=1, can_delete=True)
ClassFormSet = forms.modelformset_factory(PalletClass, fields=["kind", "label", "limit"], extra=2, can_delete=True)


@designer
def catalog(request):
    """Nośniki i klasy wysokości/wagi — dwa formsety, każdy z własnym przyciskiem zapisu."""
    which = request.POST.get("which")
    carriers = CarrierFormSet(request.POST if which == "carriers" else None, prefix="c",
                              queryset=Carrier.objects.all())
    classes = ClassFormSet(request.POST if which == "classes" else None, prefix="k",
                           queryset=PalletClass.objects.all())
    for fs in (carriers, classes):
        for i, form in enumerate(fs, start=1):
            for f in form.fields.values():
                f.widget.attrs["aria-label"] = f"{f.label} (wiersz {i})"      # pola w tabeli bez <label>
                if not isinstance(f.widget, forms.CheckboxInput):
                    f.widget.attrs.setdefault("class", "form-control")
    if request.method == "POST":
        fs = carriers if which == "carriers" else classes
        if fs.is_valid():
            fs.save()
            if which == "carriers" and Carrier.objects.filter(is_default=True).count() > 1:
                keep = Carrier.objects.filter(is_default=True).order_by("-pk").first()
                Carrier.objects.exclude(pk=keep.pk).update(is_default=False)
                messages.warning(request, f"Domyślny może być jeden nośnik — zostawiono „{keep}”.")
            messages.success(request, "Zapisano katalog.")
            return redirect("masterdata:catalog")
        messages.error(request, "Popraw zaznaczone pola.")
    return render(request, "masterdata/catalog.html", {"carriers": carriers, "classes": classes})


@designer
@require_POST
def demo(request):
    from twin.models import WarehouseModel

    wm = WarehouseModel.objects.filter(pk=request.POST.get("model") or 0).first()
    if wm is None:
        messages.error(request, "Wybierz model hali — dane demo rozkładają stan po jego regałach.")
        return redirect("masterdata:home")
    n_mat, log = services.load_demo(wm, user=request.user)
    messages.success(request, f"Dane demo: {n_mat} materiałów, {log.rows_ok} palet na stanie w „{wm.name}”.")
    return redirect("twin:warehouse_model_view", pk=wm.pk)
