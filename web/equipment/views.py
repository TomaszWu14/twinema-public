from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.roles import GROUP_ADMIN, any_role, designer, has_role
from masterdata.importers import ImportFileError

from . import importers
from .catalog import ATTACHMENTS, KINDS, capacity_at
from .models import PARAM_FIELDS, CostRate, Equipment
from core import audit
from core.models import AuditEvent

IMPORT_MAX = 5 * 1024 * 1024


class EquipmentForm(forms.ModelForm):
    attachments = forms.MultipleChoiceField(
        choices=[(k, v[0]) for k, v in ATTACHMENTS.items()], required=False, label="Osprzęt",
        widget=forms.SelectMultiple(attrs={"size": 5}),
        help_text="Zmniejsza udźwig i wydłuża obsługę palety (wartości przybliżone).")

    class Meta:
        model = Equipment
        fields = ["kind", "name", "manufacturer", "attachments", *PARAM_FIELDS, "cost_purchase",
                  "cost_purchase_max", "cost_per_hour", "cost_per_hour_max", "notes"]
        widgets = {"lift_curve": forms.Textarea(attrs={"rows": 2}), "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-control")

    def clean_lift_curve(self):
        pts = self.cleaned_data["lift_curve"] or []
        if not isinstance(pts, list) or not all(isinstance(p, list) and len(p) == 2 and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 for v in p) for p in pts):
            raise forms.ValidationError("Lista punktów [wysokość m, udźwig kg], np. [[6, 1600], [10, 1000]].")
        return sorted(pts)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Equipment.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Model o tej nazwie już jest w katalogu — wybierz inną nazwę.")   # US-022
        return name

    def clean(self):
        data = super().clean()
        for f in ("speed_loaded_kmh", "speed_empty_kmh"):
            if data.get(f) is not None and data[f] <= 0:
                self.add_error(f, "Prędkość musi być dodatnia.")
        for lo, hi in (("cost_purchase", "cost_purchase_max"), ("cost_per_hour", "cost_per_hour_max")):
            _check_range(self, data, lo, hi)
        return data


def free_name(base):
    """US-022: pierwsza wolna nazwa — „X (kopia)”, „X (kopia) 2”, … (do 120 znaków)."""
    base = base[:110]
    taken = set(Equipment.objects.filter(name__istartswith=base).values_list("name", flat=True))
    taken_lower = {t.lower() for t in taken}
    name, n = base, 1
    while name.lower() in taken_lower:
        n += 1
        name = f"{base} {n}"
    return name


def _check_range(form, data, lo, hi):
    a, b = data.get(lo), data.get(hi)
    if (a is not None and a < 0) or (b is not None and b < 0):
        form.add_error(lo, "Koszt nie może być ujemny.")
    elif a is not None and b is not None and a > b:
        form.add_error(hi, "„Do” musi być nie mniejsze niż „od”.")


class RateForm(forms.ModelForm):
    class Meta:
        model = CostRate
        fields = ["low", "high"]
        widgets = {f: forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"})
                   for f in ("low", "high")}

    def clean(self):
        data = super().clean()
        _check_range(self, data, "low", "high")
        return data


RateFormSet = forms.modelformset_factory(CostRate, form=RateForm, extra=0)


def _can_edit(user, eq):
    """Klasy systemowe zmienia tylko administrator; własny model — jego autor albo administrator.
    Model bez autora (konto usunięte) — tylko administrator."""
    if has_role(user, GROUP_ADMIN):
        return True
    return not eq.is_system and eq.created_by_id is not None and eq.created_by_id == user.pk


def _curve(eq):
    """Punkty wykresu udźwigu: od 0 do maks. wysokości (albo ostatniego punktu krzywej)."""
    top = eq.max_lift_m or max([p[0] for p in eq.lift_curve] or [0])
    if not top or not eq.lift_curve:
        return []
    return [{"h": round(top * i / 10, 2), "kg": round(capacity_at(eq.capacity_kg, eq.lift_curve, top * i / 10))}
            for i in range(11)]


@any_role
def catalog_list(request):
    kind, maker = request.GET.get("typ", ""), request.GET.get("producent", "")
    items = Equipment.objects.all()
    if kind in dict(KINDS):
        items = items.filter(kind=kind)
    if maker:
        items = items.filter(manufacturer=maker)
    makers = Equipment.objects.exclude(manufacturer="").order_by("manufacturer").values_list(
        "manufacturer", flat=True).distinct()
    return render(request, "equipment/list.html", {"items": items, "kinds": KINDS, "kind": kind,
                                                   "makers": makers, "maker": maker})


@designer
def import_template(request):
    resp = HttpResponse(importers.template_xlsx(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="twinema_wzor_sprzetu.xlsx"'
    return resp


@designer
@require_POST
def import_file(request):
    f = request.FILES.get("plik")
    if not f or f.size > IMPORT_MAX:
        messages.error(request, "Wybierz plik xlsx/csv (do 5 MB).")
        return redirect("equipment:list")
    try:
        rows, bad = importers.parse_file(f.name, f.read())
    except ImportFileError as exc:
        messages.error(request, str(exc))
        return redirect("equipment:list")
    created, updated, skipped = importers.import_rows(rows, request.user)
    audit.record(request, AuditEvent.IMPORT, object_type="import sprzętu", label=f.name[:200],
                 detail=f"nowe: {created}, zaktualizowane: {updated}, pominięte: {len(skipped)}")
    messages.success(request, f"Import: {created} nowych, {updated} zaktualizowanych modeli.")
    for n, why in bad[:20]:
        messages.warning(request, f"Wiersz {n}: {why}")
    for name, why in skipped[:20]:
        messages.warning(request, f"„{name}”: {why}")
    if len(bad) + len(skipped) > 40:
        messages.warning(request, f"…i {len(bad) + len(skipped) - 40} kolejnych odrzuceń.")
    return redirect("equipment:list")


@any_role
def catalog_detail(request, pk):
    eq = get_object_or_404(Equipment, pk=pk)
    rows = [(Equipment._meta.get_field(f).verbose_name, getattr(eq, f)) for f in PARAM_FIELDS if f != "lift_curve"]
    for label, lo, hi in (("Koszt zakupu [zł]", "cost_purchase", "cost_purchase_max"),
                          ("Koszt godziny pracy [zł]", "cost_per_hour", "cost_per_hour_max")):
        r = eq.cost_range(lo, hi)
        rows.append((label, f"{r[0]:,.0f} – {r[1]:,.0f}".replace(",", " ") if r else None))
    if eq.attachments:
        rows.insert(0, ("Udźwig z osprzętem [kg]", eq.params()["capacity_kg"]))
    curve = _curve(eq)
    top = max([c["kg"] for c in curve] or [1])
    return render(request, "equipment/detail.html", {
        "eq": eq, "rows": rows, "curve": curve, "can_edit": _can_edit(request.user, eq),
        "bars": [{**c, "pct": round(100 * c["kg"] / top)} for c in curve],
        "racks": eq.racks.count(), "scenarios": eq.scenarios.count()})


@designer
def catalog_form(request, pk=None):
    eq = get_object_or_404(Equipment, pk=pk) if pk else None
    if eq and not _can_edit(request.user, eq):
        return render(request, "core/403.html", status=403)
    form = EquipmentForm(request.POST or None, instance=eq)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not eq:
            obj.created_by = request.user
        obj.save()
        messages.success(request, f"Zapisano „{obj}”.")
        return redirect("equipment:detail", pk=obj.pk)
    return render(request, "equipment/form.html", {"form": form, "eq": eq})


@designer
@require_POST
def catalog_copy(request, pk):
    src = get_object_or_404(Equipment, pk=pk)
    src.pk, src.is_system, src.created_by = None, False, request.user
    src.name = free_name(f"{src.name} (kopia)")
    src.save()
    messages.success(request, "Skopiowano jako własny model — wpisz parametry z karty katalogowej.")
    return redirect("equipment:edit", pk=src.pk)


@designer
def catalog_delete(request, pk):
    eq = get_object_or_404(Equipment, pk=pk)
    if eq.is_system or not _can_edit(request.user, eq):
        return render(request, "core/403.html", status=403)
    if request.method != "POST":                         # US-004: najpierw ekran potwierdzenia ze skutkami
        from core.deletion import confirm, equipment_effects
        removed, detached = equipment_effects(eq)
        return confirm(request, title="Usuń model sprzętu", name=eq.name, removed=removed, detached=detached,
                       cancel_url=reverse("equipment:detail", args=[eq.pk]), confirm_label="Tak, usuń model")
    name, groups = eq.name, eq.scenario_fleets.count()
    audit.record(request, AuditEvent.DELETE, eq, object_type="model sprzętu", detail=f"grupy floty mieszanej: {groups}")
    eq.delete()
    msg = f"Usunięto „{name}” — regały i flota jednorodna scenariuszy z tym sprzętem wracają do ustawień ogólnych."
    if groups:
        msg += f" Usunięto też grupy floty mieszanej z tym sprzętem: {groups}."
    messages.success(request, msg)
    return redirect("equipment:list")


@designer
def rates(request):
    """Stawki kosztowe (C1) — widełki od–do; edytuje Projektant i administrator, Podgląd widzi tylko wyniki."""
    formset = RateFormSet(request.POST or None, queryset=CostRate.objects.all())
    if request.method == "POST":
        if formset.is_valid():
            formset.save()
            messages.success(request, "Zapisano stawki — koszty w wynikach symulacji przeliczą się przy wyświetleniu.")
            return redirect("equipment:rates")
        messages.error(request, "Popraw zaznaczone stawki.")
    return render(request, "equipment/rates.html", {"formset": formset})
