"""Klej Django ↔ symulacja dnia (`scenario.sim` jest czystym Pythonem)."""
import time

from equipment.catalog import FLEET_ROLE, move_minutes
from equipment.models import CostRate
from masterdata.packaging import weighted_cartons_per_pallet
from masterdata.services import cartons_per_pallet_distribution as cartons_distribution
from masterdata.services import stock_profile
from twin.blender_scene import model_floor, model_racks
from twin.design_kpi import rack_to_element, travel_stats
from twin.layout import feature_row, rack_row
from twin.shared import hall_feature_dict

from . import costs
from .models import ScenarioRun
from .placement import check_placement
from .sim import run_many
from .sim.places import needed_roles, places_from_features

MAX_RUNS = 30
KEEP_RUNS = 20                  # ostatnie symulacje na scenariusz; starsze (z dużym JSON zdarzeń) usuwamy


def simulate(day, wm, *, runs=12, user=None):
    sc = day.scenario
    sim_day = day.sim_day()
    places = places_from_features([hall_feature_dict(f) for f in wm.features.all()], needed_roles(sim_day))
    t0 = time.perf_counter()
    params, cpp = sc.sim_params(), cartons_distribution()
    if cpp:
        # kartonów/paletę z master daty (rozkład po stanie) zastępuje średnią normę scenariusza
        params.update(cpp_dist=cpp[0], cartons_per_pallet=weighted_cartons_per_pallet(cpp[0]))
    groups = fleet_groups_for(sc, wm)
    fleet = None
    if groups:                                  # K3: flota mieszana — grupy z katalogu, udział VNA z layoutu
        positions, _ = _layout_costs_input(wm)
        params.update(fleet_groups=groups, fleet_units=sum(g["units"] for g in groups),
                      vna_share=positions["vna"] / max(1, positions["vna"] + positions["reach"]))
    elif sc.fleet_equipment_id and (fleet := fleet_from_catalog(sc.fleet_equipment, wm)):
        params.update(fleet_min_per_move=fleet["min_per_move"], battery_h=fleet["battery_h"], charge_h=fleet["charge_h"])
    res = run_many(sim_day, params, sc.shift_dicts(), places, sc.seed, runs=runs)
    res["fleet"] = fleet
    res["fleet_groups"] = [{k: g[k] for k in ("name", "kind", "role", "units", "min_per_move", "leg_min",
                                              "battery_h", "charge_h", "dist_m", "lift_m")} for g in groups]
    res["cpp"] = {"value": params["cartons_per_pallet"], "source": f"master data ({cpp[2]})" if cpp else "norma"}
    res["placement"] = placement_for(wm, sc.growth)
    res["bottlenecks"] = placement_bottlenecks(res["placement"]) + res["bottlenecks"]
    run = ScenarioRun.objects.create(
        scenario=sc, day_kind=day.kind, model=wm, runs=runs, seed=sc.seed,
        duration_s=round(time.perf_counter() - t0, 2), events=(ev := res.pop("events")), has_events=bool(ev), result=res, created_by=user)
    prune_runs(sc)
    return run


def fleet_from_catalog(eq, wm, rack_class=None):
    """Sprzęt floty z katalogu (K1) → czas ruchu palety na tym layoucie: średnia droga od punktów obsługi
    (doki, stanowiska) do miejsc paletowych (`travel_stats`) tam i z powrotem + podniesienie na średnią wysokość
    belki + pobranie/odłożenie; bateria i ładowanie z katalogu. Półki (kompletacja ręczna) pomijamy.
    `rack_class` ("vna" | "pallet") — tylko regały tej klasy (K3: grupa floty liczona na swoich regałach),
    brak takich regałów → wszystkie."""
    racks = [r for r in model_racks(wm) if r["rack_class"] != "shelf"]
    racks = [r for r in racks if r["rack_class"] == rack_class] or racks
    p = eq.params()
    if not racks:
        dist, lift = 0.0, 0.0
    else:
        floor = model_floor(wm, racks)
        tr = travel_stats([rack_to_element(r) for r in racks], [hall_feature_dict(f) for f in wm.features.all()],
                          floor["width"], floor["depth"])
        w = [r["n_bays"] * r["n_levels"] for r in racks]
        dist = tr["avg_m"] or 0.0
        lift = sum((r["n_levels"] - 1) / 2 * r["level_h"] * k for r, k in zip(racks, w, strict=True)) / sum(w)
    return {"name": eq.name, "dist_m": round(dist, 1), "lift_m": round(lift, 2),
            "min_per_move": round(move_minutes(p, dist, lift), 2),
            "battery_h": p["battery_h"] or 8.0, "charge_h": p["charge_h"] or 1.5}


VNA_LEG_SHARE = 1 / 3      # ponytail: etap VNA = ⅓ średniej drogi (punkt przekazania u czoła alejki) — z layoutu, gdy zaznaczymy punkty przekazania


def fleet_groups_for(sc, wm):
    """K3: grupy floty mieszanej scenariusza → `engine.FleetMix`. Czas jednego ruchu (`min_per_move`) jak
    w `fleet_from_catalog` na regałach roli grupy; etap przy przekazaniu (`leg_min`): transport = sama jazda
    bez podnoszenia, VNA = krótszy odcinek + podniesienie. Bez grup → [] (dawna jedna flota)."""
    groups = []
    for f in sc.fleet.select_related("equipment"):
        eq, role = f.equipment, FLEET_ROLE.get(f.equipment.kind)
        if not role:
            continue
        c = fleet_from_catalog(eq, wm, "vna" if role == "vna" else "pallet")
        dist, lift, p = c["dist_m"], c["lift_m"], eq.params()
        leg = (move_minutes(p, dist, 0) if role == "transport" else
               move_minutes(p, dist * VNA_LEG_SHARE, lift) if role == "vna" else c["min_per_move"])
        groups.append({**c, "kind": eq.kind, "role": role, "units": f.units, "leg_min": round(leg, 2)})
    return groups


def placement_for(wm, growth):
    """Pojemność vs potrzeba i reguły rozmieszczenia na aktualnym layoucie i stanie (`placement`)."""
    return check_placement([rack_row(r) for r in wm.racks.order_by("pk")],
                           [feature_row(f) for f in wm.features.order_by("pk")], stock_profile(), growth)


FIX = {"capacity": "dołóż regały / poziomy w edytorze albo zmniejsz zapas (mnożnik, dni zapasu)",
       "zone": "powiększ strefę w edytorze albo przesuń do niej regały",
       "load": "podnieś nośność belek w części regałów (pole „nośność” regału) albo obniż palety",
       "heavy": "zarezerwuj dolne poziomy na ciężkie palety albo dodaj regały niskie"}


def placement_bottlenecks(pl):
    """Problemy pojemności/rozmieszczenia w formacie wąskich gardeł symulacji (na górze listy)."""
    def fix(code):
        return FIX["capacity" if code.startswith("capacity") else "load" if code == "load_over"
                   else "heavy" if code == "heavy_high" else "zone"]
    return [{"severity": i["severity"], "area": "Pojemność i rozmieszczenie", "where": "", "window": "",
             "problem": i["message"], "suggestion": fix(i["code"])} for i in pl["issues"]]


def _shift_hours(sh):
    length = sh["end_h"] - sh["start_h"] + (24 if sh["end_h"] <= sh["start_h"] else 0)
    return max(0.0, length - sh["break_min"] / 60) * sh["people"]


def _memo(memo, key, fn):
    if key not in memo:
        memo[key] = fn()
    return memo[key]


def _layout_costs_input(wm):
    positions = {"reach": 0, "vna": 0, "shelf": 0}
    for r in model_racks(wm):
        p = rack_to_element(r)["params"]
        positions[{"pallet": "reach"}.get(r["rack_class"], r["rack_class"])] += p["bays"] * p["levels"] * p["pallets_per_bay"]
    return positions, list(wm.features.values_list("kind", flat=True))


def _cost_range(eq, lo, hi):
    return eq.cost_range(lo, hi) if eq else None


def _fleet_costs_input(run):
    """Flota do kosztów: grupy floty mieszanej z przebiegu (K3) — godziny pracy dzielone wg udziału grup
    w przebiegu reprezentatywnym — albo jedna flota scenariusza (`fleet_equipment` / norma)."""
    sc, groups = run.scenario, run.result.get("rep", {}).get("kpi", {}).get("fleet_groups") or []
    if groups and run.result.get("fleet_groups"):
        eqs = {f.equipment.name: f.equipment for f in sc.fleet.select_related("equipment")}
        total = sum(g["busy_h"] for g in groups) or 1
        return [{"name": g["name"], "units": g["units"], "share": g["busy_h"] / total,
                 "purchase": _cost_range(eqs.get(g["name"]), "cost_purchase", "cost_purchase_max"),
                 "hour": _cost_range(eqs.get(g["name"]), "cost_per_hour", "cost_per_hour_max")} for g in groups]
    eq = sc.fleet_equipment
    return [{"name": eq.name if eq else "wózki", "units": sc.fleet_units, "share": 1,
             "purchase": _cost_range(eq, "cost_purchase", "cost_purchase_max"),
             "hour": _cost_range(eq, "cost_per_hour", "cost_per_hour_max")}]


def run_costs(run, rates=None, memo=None):
    """Koszty wyniku symulacji (C1) — liczone przy wyświetleniu, więc zmiana stawek działa od razu.
    Layout = aktualny stan modelu hali (jak pojemność w `placement_for`). `memo` — słownik współdzielony
    przez kilka wywołań w jednym żądaniu (R3: stawki, layout, dni i zmiany czytane raz, nie per przebieg)."""
    memo = {} if memo is None else memo
    rates = rates or _memo(memo, "rates", CostRate.as_dict)
    sc, wm = run.scenario, run.model
    positions, kinds = _memo(memo, ("layout", wm.pk), lambda: _layout_costs_input(wm))
    fleet = _fleet_costs_input(run)
    # miks dni w roku: ta symulacja + najnowsza symulacja drugiego typu dnia na tym samym modelu
    by_kind = {run.day_kind: run}
    other = "peak" if run.day_kind == "typical" else "typical"
    if (o := _memo(memo, ("run", sc.pk, wm.pk, other), lambda: ScenarioRun.objects.filter(
            scenario=sc, model=wm, day_kind=other).defer("events").order_by("-created_at").first())):
        by_kind[other] = o
    sc_days = _memo(memo, ("days", sc.pk), lambda: {d.kind: d for d in sc.days.all()})
    days = []
    for kind, n in costs.mix_days(sc.work_days, sc.peak_days_year, "peak" in by_kind, "typical" in by_kind):
        a, day = by_kind[kind].result["agg"], sc_days.get(kind)
        busy = (a["fleet_busy_h"]["mean"] if "fleet_busy_h" in a          # stare przebiegi: odtwarzane z %
                else a["fleet_util_pct"]["mean"] / 100 * sum(f["units"] for f in fleet) * 24)
        days.append({"kind": kind, "days": n, "fleet_busy_h": busy,
                     "volumes": {"pallets": a["pallets_in"]["mean"] + a["pallets_out"]["mean"],
                                 "parcels": a["parcels"]["mean"], "orders": (day.orders_avg * sc.growth) if day else 0}})
    return costs.compute(
        rates, {"positions": positions, "docks": kinds.count("dock"), "stations": kinds.count("station"),
                "area_m2": wm.floor_width_m * wm.floor_depth_m},
        fleet, _memo(memo, ("shift_h", sc.pk), lambda: sum(_shift_hours(s) for s in sc.shift_dicts())), days)


def prune_runs(sc):
    """Zostawia KEEP_RUNS ostatnich przebiegów scenariusza. US-025: wynik przypięty do prezentacji 3D
    nie wypada z limitu — pokaz nie traci danych."""
    old = ScenarioRun.objects.filter(scenario=sc, showcases__isnull=True).values_list("pk", flat=True)[KEEP_RUNS:]
    ScenarioRun.objects.filter(pk__in=list(old)).delete()
