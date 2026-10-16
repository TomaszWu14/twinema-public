import re

from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from equipment.catalog import FLEET_ROLE

from core.roles import GROUP_ADMIN, GROUP_DESIGNER, any_role, designer, has_role

from twin.models import WarehouseModel

from .inbound import _hhmm
from .models import InboundStream, OutboundStream, Scenario, ScenarioDay, ScenarioFleet, Shift
from .staffing import cutoff_risk, process_hours, staffing
from .views_sim import SimForm, _sim_view

KIND_LABEL = dict(InboundStream._meta.get_field("kind").choices)
OUT_LABEL = dict(OutboundStream._meta.get_field("kind").choices)
LEVELS = ("avg", "max")


def _fc(widget):
    widget.attrs.setdefault("class", "form-control")
    return widget


class HourField(forms.Field):
    """Godzina jako GG:MM (np. 13:30, 24:00 = koniec doby) ↔ liczba godzin w bazie (13.5)."""
    widget = forms.TextInput
    PATTERN = re.compile(r"^\s*(\d{1,2})(?::([0-5]\d))?\s*$")

    def widget_attrs(self, widget):
        return {"class": "form-control", "inputmode": "numeric", "placeholder": "GG:MM",
                "pattern": r"\d{1,2}(:[0-5]\d)?", "size": 5}

    def prepare_value(self, value):
        if isinstance(value, (int, float)):
            m = round(value * 60)
            return f"{m // 60:02d}:{m % 60:02d}"
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        m = self.PATTERN.match(str(value))
        if not m:
            raise forms.ValidationError("Godzina w formacie GG:MM, np. 13:30.")
        h = int(m.group(1)) + int(m.group(2) or 0) / 60
        if h > 24:
            raise forms.ValidationError("Godzina 0:00–24:00.")
        return h


class ScenarioForm(forms.ModelForm):
    class Meta:
        model = Scenario
        fields = ["name", "description", "growth", "seed", "shift_h", "work_days", "peak_days_year", *Scenario.NORM_FIELDS,
                  "return_restock_pct", *Scenario.FLEET_FIELDS, "fleet_equipment"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fe = self.fields["fleet_equipment"]
        fe.queryset = fe.queryset.exclude(kind__in=("conveyor", "sorter"))
        fe.empty_label = "— bez katalogu (norma min/ruch i bateria z pól powyżej) —"
        self.fields["peak_days_year"].required = False      # stary formularz bez pola → wartość bez zmian
        for f in self.fields.values():
            _fc(f.widget)

    def clean_peak_days_year(self):
        v = self.cleaned_data.get("peak_days_year")
        return self.instance.peak_days_year if v is None else v


class NewScenarioForm(forms.ModelForm):
    class Meta:
        model = Scenario
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control", "maxlength": 200})}


class DayProfileForm(forms.ModelForm):
    class Meta:
        model = ScenarioDay
        fields = ScenarioDay.PROFILE_FIELDS
        widgets = {f: _fc(forms.NumberInput(attrs={"step": "any", "min": 0})) for f in ScenarioDay.PROFILE_FIELDS}


def _num(fields):
    return {f: _fc(forms.NumberInput(attrs={"step": "any", "min": 0})) for f in fields}


IN_FIELDS = ["kind", "arrivals_min", "arrivals_avg", "arrivals_max", "pallets_min", "pallets_avg",
             "pallets_max", "window_from", "window_to", "mono_pct", "inspect_pct", "inspect_min"]
OUT_FIELDS = ["kind", "departures_min", "departures_avg", "departures_max", "pallets_min", "pallets_avg",
              "pallets_max", "window_from", "window_to"]
SHIFT_FIELDS = ["process", "start_h", "end_h", "break_min", "people"]


class InForm(forms.ModelForm):
    window_from = HourField(label="Okno od")
    window_to = HourField(label="Okno do")


class OutForm(forms.ModelForm):
    window_from = HourField(label="Załadunek od")
    window_to = HourField(label="Cut-off")


class ShiftForm(forms.ModelForm):
    start_h = HourField(label="Od")
    end_h = HourField(label="Do")


StreamFormSet = forms.modelformset_factory(
    InboundStream, form=InForm, fields=IN_FIELDS, extra=1, can_delete=True,
    widgets=_num(f for f in IN_FIELDS if f not in ("kind", "window_from", "window_to")) | {"kind": _fc(forms.Select())})
OutFormSet = forms.modelformset_factory(
    OutboundStream, form=OutForm, fields=OUT_FIELDS, extra=1, can_delete=True,
    widgets=_num(f for f in OUT_FIELDS if f not in ("kind", "window_from", "window_to")) | {"kind": _fc(forms.Select())})
ShiftFormSet = forms.modelformset_factory(
    Shift, form=ShiftForm, fields=SHIFT_FIELDS, extra=1, can_delete=True,
    widgets=_num(["break_min", "people"]) | {"process": _fc(forms.Select())})



class FleetForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        eq = self.fields["equipment"]
        eq.queryset = eq.queryset.filter(kind__in=FLEET_ROLE)          # bez przenośników i sorterów
        eq.widget.attrs["class"] = "form-control"


FleetFormSet = forms.modelformset_factory(
    ScenarioFleet, form=FleetForm, fields=["equipment", "units"], extra=1, can_delete=True,
    widgets=_num(["units"]))


def _results(day, shifts):
    r = {"day": day}
    for lvl in LEVELS:
        i, o = day.demand(lvl), day.outbound_demand(lvl)
        st = staffing(process_hours(i, o), shifts)
        r[lvl] = {"in": i, "out": o, "staff": st, "short": [p["label"] for p in st if p["short"]],
                  "cutoff": cutoff_risk(o["person_hours"]["pack"], shifts, o["courier_cutoff"])}
    return r


def _arrival_rows(results, side="in", label=KIND_LABEL):
    """Wiersz na typ auta: komórki w kolejności kolumn tabeli (dzień × poziom)."""
    out = {}
    for r in results:
        for level in LEVELS:
            for row in r[level][side]["rows"]:
                out.setdefault(row["kind"], {"label": label[row["kind"]], "cells": {}})
                out[row["kind"]]["cells"][(r["day"].kind, level)] = row
    cols = [(r["day"].kind, lvl) for r in results for lvl in LEVELS]
    return [{"label": v["label"], "cells": [v["cells"].get(c) for c in cols]} for v in out.values()]


def _staff_rows(results, shifts):
    """Obsada: wiersz na proces × zmianę; kolumny = zakładana + potrzebna dla (dzień × poziom)."""
    rows = []
    cols = [r[lvl]["staff"] for r in results for lvl in LEVELS]
    for i, proc in enumerate(cols[0]):
        own = proc["shifts"] or [None]
        for j, sh in enumerate(own):
            cells = []
            for col in cols:
                p = col[i]
                if sh is None:
                    cells.append({"needed": "—" if not p["hours"] else "brak zmiany", "short": p["short"]})
                else:
                    c = p["shifts"][j]
                    cells.append({"needed": c["needed"], "short": c["gap"] < 0, "gap": c["gap"]})
            when = f"{_hhmm(sh['start_h'])}–{_hhmm(sh['end_h'])}" if sh else ""
            rows.append({"label": proc["label"] if j == 0 else "", "shift": sh, "when": when, "cells": cells,
                         "first": j == 0, "span": len(own)})
    return rows


def _hours_rows(results):
    """Osobogodziny: wiersz na proces, komórki w kolejności kolumn (dzień × poziom)."""
    cols = [r[lvl]["staff"] for r in results for lvl in LEVELS]
    return [{"label": p["label"], "cells": [col[i]["hours"] for col in cols]} for i, p in enumerate(cols[0])]


@any_role
def scenario_list(request):
    raw = request.GET.get("model", "")                # R4: przyszedł z „Symuluj scenariusz na tej hali”
    target = WarehouseModel.objects.filter(pk=raw).only("pk", "name").first() if raw.isdigit() else None
    return render(request, "scenario/list.html", {
        "form": NewScenarioForm(), "scenarios": Scenario.objects.select_related("created_by")[:50],
        "target_model": target, "model_pk": target.pk if target else None})


@designer
@require_POST
def scenario_create(request):
    form = NewScenarioForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Wpisz nazwę scenariusza.")
        return redirect("scenario:list")
    sc = form.save(commit=False)
    sc.created_by = request.user
    sc.save()
    sc.ensure_days()
    messages.success(request, f"Utworzono scenariusz „{sc}” z przykładowym planem przyjęć, wydań i obsady — "
                              "popraw liczby.")
    return redirect("scenario:detail", pk=sc.pk)


@designer
@require_POST
def scenario_demo(request):
    """R4: scenariusz referencyjny (dane syntetyczne) + hala demo jednym przyciskiem zamiast manage.py.
    Idempotentnie — ponowne kliknięcie odtwarza ten sam plan."""
    from io import StringIO

    from django.core.management import call_command

    from .management.commands.demo_scenariusz import NAME
    call_command("demo_scenariusz", stdout=StringIO())
    sc = Scenario.objects.get(name=NAME)
    messages.success(request, f"Wczytano scenariusz demo „{sc}” z halą do symulacji — dane syntetyczne.")
    return redirect("scenario:detail", pk=sc.pk)


@any_role
def scenario_detail(request, pk):
    sc = get_object_or_404(Scenario, pk=pk)
    days = list(sc.days.prefetch_related("inbound", "outbound"))
    if len(days) < len(ScenarioDay.KIND_CHOICES):   # R3: dni zakłada tworzenie scenariusza; tu tylko brakujące
        sc.ensure_days(with_defaults=False)          # (np. utworzony z ORM) — zwykły GET nic nie zapisuje
        days = list(sc.days.prefetch_related("inbound", "outbound"))
    shifts = sc.shift_dicts()
    results = [_results(d, shifts) for d in days]
    ctx = {"sc": sc, "results": results, "arrival_rows": _arrival_rows(results),
           "departure_rows": _arrival_rows(results, "out", OUT_LABEL), "staff_rows": _staff_rows(results, shifts),
           "hours_rows": _hours_rows(results),
           "ncols": 1 + 2 * len(results)}
    sim_runs, memo = [], {}                     # memo: koszty obu przebiegów czytają stawki/layout/dni raz (R3)
    runs = [r for kind, _ in ScenarioDay.KIND_CHOICES
            if (r := sc.runs.defer("events").select_related("model", "scenario__fleet_equipment")
                .filter(day_kind=kind).first())]
    for r in runs:                              # najnowszy przebieg danego dnia = „drugi dzień” miksu kosztów
        memo[("run", sc.pk, r.model_id, r.day_kind)] = r
    sim_runs = [_sim_view(r, memo) for r in runs]
    ctx["sim_runs"] = sim_runs
    ctx["sim_charts"] = {f"sim-{v['run'].pk}": v["chart"] for v in sim_runs}
    if has_role(request.user, GROUP_ADMIN, GROUP_DESIGNER):
        # model z linku „Symuluj na tej hali” (widok modelu) > ostatnio symulowany > pierwszy
        asked = request.GET.get("model", "")
        first = WarehouseModel.objects.values_list("pk", flat=True).first()
        if first is None:
            ctx["no_models"] = True                 # pusty stan: najpierw hala (generator), potem symulacja
        else:
            last = sim_runs[0]["run"].model_id if sim_runs else None
            ctx["sim_form"] = SimForm(initial={"model": int(asked) if asked.isdigit() else last or first})
        section, data = _retry(request, sc)          # US-021: formularz z błędem wraca z wpisanymi danymi

        def bound(name):
            return data if section == name else None
        ctx["form"] = ScenarioForm(bound("params"), instance=sc)
        ctx["day_forms"] = [{"day": d,
                             "inbound": StreamFormSet(bound(f"in:{d.kind}"), queryset=d.inbound.all(), prefix=d.kind),
                             "outbound": OutFormSet(bound(f"out:{d.kind}"), queryset=d.outbound.all(),
                                                    prefix=f"{d.kind}-out"),
                             "profile": DayProfileForm(bound(f"out:{d.kind}"), instance=d, prefix=f"{d.kind}-p")}
                            for d in days]
        ctx["shift_fs"] = ShiftFormSet(bound("shift"), queryset=sc.shifts.all(), prefix="shift")
        ctx["fleet_fs"] = FleetFormSet(bound("fleet"), queryset=sc.fleet.all(), prefix="fleet")
        from masterdata.services import cartons_per_pallet_hint     # podpowiedź, nie nadpisuje normy
        ctx["cpp_hint"] = cartons_per_pallet_hint()
    return render(request, "scenario/detail.html", ctx)


RETRY_KEY = "scenario_retry"


def _remember(request, pk, section):
    """US-021: wpisane dane formularza z błędem → sesja; ekran scenariusza odtworzy je raz, z błędami przy polach."""
    data = {k: v for k, v in request.POST.lists() if k != "csrfmiddlewaretoken"}
    request.session[RETRY_KEY] = {"pk": pk, "section": section, "data": data}


def _retry(request, sc):
    """(sekcja, QueryDict) zapamiętane po błędzie dla tego scenariusza albo (None, None); jednorazowo."""
    from django.http import QueryDict
    saved = request.session.pop(RETRY_KEY, None)
    if not saved or saved.get("pk") != sc.pk:
        return None, None
    data = QueryDict(mutable=True)
    for k, values in saved["data"].items():
        data.setlist(k, values)
    return saved["section"], data


def _errors(request, title, fs=None, form=None):
    if form is not None:
        for errs in form.errors.values():
            messages.error(request, f"{title}: {' '.join(errs)}")
    if fs is not None:
        for i, errs in enumerate(fs.errors):
            for msg in [e for v in errs.values() for e in v]:
                messages.error(request, f"{title}, wiersz {i + 1}: {msg}")
        for msg in fs.non_form_errors():
            messages.error(request, f"{title}: {msg}")


def _save_formset(fs, **parent):
    for obj in fs.save(commit=False):
        for k, v in parent.items():
            setattr(obj, k, v)
        obj.save()
    for obj in fs.deleted_objects:
        obj.delete()


@designer
@require_POST
def scenario_save(request, pk):
    sc = get_object_or_404(Scenario, pk=pk)
    form = ScenarioForm(request.POST, instance=sc)
    if form.is_valid():
        form.save()
        messages.success(request, "Zapisano parametry i normy — wyniki przeliczone.")
    else:
        _errors(request, "Parametry", form=form)
        _remember(request, pk, "params")
    return redirect("scenario:detail", pk=pk)


@designer
@require_POST
def day_save(request, pk, kind):
    day = get_object_or_404(ScenarioDay, scenario_id=pk, kind=kind)
    fs = StreamFormSet(request.POST, queryset=day.inbound.all(), prefix=kind)
    if not fs.is_valid():
        _errors(request, day.get_kind_display(), fs=fs)
        _remember(request, pk, f"in:{kind}")
        return redirect("scenario:detail", pk=pk)
    with transaction.atomic():
        _save_formset(fs, day=day)
        day.scenario.save(update_fields=["updated_at"])
    messages.success(request, f"Zapisano plan przyjęć: {day.get_kind_display().lower()} — wyniki przeliczone.")
    return redirect("scenario:detail", pk=pk)


@designer
@require_POST
def outbound_save(request, pk, kind):
    day = get_object_or_404(ScenarioDay, scenario_id=pk, kind=kind)
    fs = OutFormSet(request.POST, queryset=day.outbound.all(), prefix=f"{kind}-out")
    form = DayProfileForm(request.POST, instance=day, prefix=f"{kind}-p")
    if not (fs.is_valid() and form.is_valid()):
        _errors(request, f"Wydania — {day.get_kind_display().lower()}", fs=fs, form=form)
        _remember(request, pk, f"out:{kind}")
        return redirect("scenario:detail", pk=pk)
    with transaction.atomic():
        form.save()
        _save_formset(fs, day=day)
        day.scenario.save(update_fields=["updated_at"])
    messages.success(request, f"Zapisano wydania, paczki i zwroty: {day.get_kind_display().lower()}.")
    return redirect("scenario:detail", pk=pk)


@designer
@require_POST
def shifts_save(request, pk):
    sc = get_object_or_404(Scenario, pk=pk)
    fs = ShiftFormSet(request.POST, queryset=sc.shifts.all(), prefix="shift")
    if not fs.is_valid():
        _errors(request, "Obsada", fs=fs)
        _remember(request, pk, "shift")
        return redirect("scenario:detail", pk=pk)
    with transaction.atomic():
        _save_formset(fs, scenario=sc)
        sc.save(update_fields=["updated_at"])
    messages.success(request, "Zapisano obsadę i zmiany — porównanie z potrzebą przeliczone.")
    return redirect("scenario:detail", pk=pk)


@designer
@require_POST
def fleet_save(request, pk):
    sc = get_object_or_404(Scenario, pk=pk)
    fs = FleetFormSet(request.POST, queryset=sc.fleet.all(), prefix="fleet")
    if not fs.is_valid():
        _errors(request, "Flota", fs=fs)
        _remember(request, pk, "fleet")
        return redirect("scenario:detail", pk=pk)
    with transaction.atomic():
        _save_formset(fs, scenario=sc)
        sc.save(update_fields=["updated_at"])
    messages.success(request, "Zapisano flotę mieszaną — uruchom symulację ponownie, by zobaczyć wynik.")
    return redirect(reverse("scenario:detail", args=[pk]) + "#sc-fleet-h")


@designer
@require_POST
def scenario_copy(request, pk):
    src = get_object_or_404(Scenario, pk=pk)
    with transaction.atomic():
        days = list(src.days.prefetch_related("inbound", "outbound"))
        shifts = list(src.shifts.all())
        fleet = list(src.fleet.all())
        sc = Scenario.objects.get(pk=pk)
        sc.pk, sc.name, sc.created_by = None, f"{src.name} (kopia)"[:200], request.user
        sc.save()
        for d in days:
            streams = [*d.inbound.all(), *d.outbound.all()]
            d.pk, d.scenario = None, sc
            d.save()
            for s in streams:
                s.pk, s.day = None, d
                s.save()
        for s in [*shifts, *fleet]:
            s.pk, s.scenario = None, sc
            s.save()
    messages.success(request, f"Skopiowano scenariusz jako „{sc}”.")
    return redirect("scenario:detail", pk=sc.pk)


@designer
def scenario_delete(request, pk):
    sc = get_object_or_404(Scenario, pk=pk)
    if request.method != "POST":                         # US-004: najpierw ekran potwierdzenia ze skutkami
        from core.deletion import confirm, scenario_effects
        removed, detached = scenario_effects(sc)
        return confirm(request, title="Usuń scenariusz", name=sc.name, removed=removed, detached=detached,
                       cancel_url=reverse("scenario:detail", args=[sc.pk]), confirm_label="Tak, usuń scenariusz")
    name = sc.name
    sc.delete()
    messages.success(request, f"Usunięto scenariusz „{name}”.")
    return redirect("scenario:list")
