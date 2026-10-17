# Auto-split from the former monolithic views.py. Feature views live in
# sibling modules; shared imports/constants/helpers stay in core.py.
from twin.shared import (
    _md_role, _parse_location_code, _planner, cache_digest, Count, get_object_or_404,
    HALL_FEATURE_COLORS, hall_feature_dict, hall_feature_kinds, messages, model_columns,
    redirect, render, safe_json, save_hall_features, transaction,
    WarehouseHallFeature, WarehouseModel, WarehouseModelRack,
)
from django.urls import reverse

from twin.addressing import parse_bay_numbers
from twin.blender_route import rack_corners
from twin.blender_scene import rack_class
from twin.ewm_service import active_master
from twin.model_geometry import floor_size, is_geometry_csv, parse_geometry_csv
from twin.models import BayTemplate, WarehouseTaskBatch
from twin.signals import touch_model
from core import audit
from core.models import AuditEvent


@_planner
def warehouse_model_list(request):
    models_qs = WarehouseModel.objects.annotate(rack_count=Count("racks"))
    return render(request, "twin/warehouse_model/list.html", {"models": models_qs})

@_md_role
def warehouse_model_upload(request):
    from twin.forms import WarehouseModelForm
    if request.method == "POST":
        form = WarehouseModelForm(request.POST)
        f = request.FILES.get("location_file")
        if not f:
            messages.error(request, "Wybierz plik z lokalizacjami.")
            return render(request, "twin/warehouse_model/upload.html", {"form": form})
        if f.size > 5 * 1024 * 1024:
            messages.error(request, "Plik zbyt duży (max 5 MB).")
            return render(request, "twin/warehouse_model/upload.html", {"form": form})
        if form.is_valid():
            # Parsuj PRZED zapisem, żeby błąd w połowie nie zostawił osieroconego modelu.
            text = f.read().decode("utf-8-sig", errors="ignore")
            if is_geometry_csv(text):
                return _create_from_geometry(request, form, text)
            rack_map = {}  # (zone, rack) → {bays, levels}
            skipped = 0
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # accept comma or tab separated; first column is location code
                parts = line.replace('\t', ',').split(',')
                code = parts[0].strip()
                parsed = _parse_location_code(code)
                if not parsed:
                    if code:
                        skipped += 1        # policz nierozpoznane — inaczej cicha utrata danych
                    continue
                zone, rack, bay, lvl, lvl_num = parsed
                key = (zone, rack)
                if key not in rack_map:
                    rack_map[key] = {"bays": set(), "levels": 0}
                rack_map[key]["bays"].add(bay)
                rack_map[key]["levels"] = max(rack_map[key]["levels"], lvl_num)
            # Model + regały all-or-nothing (jak warehouse_model_coords/generator).
            with transaction.atomic():
                wm = form.save()
                WarehouseModelRack.objects.bulk_create([
                    WarehouseModelRack(model=wm, zone=zone, rack_id=rack,
                                       n_bays=len(data["bays"]), n_levels=data["levels"])
                    for (zone, rack), data in sorted(rack_map.items())
                ])
            msg = f"Wczytano {len(rack_map)} regałów z pliku."
            if skipped:
                msg += f" Pominięto {skipped} nierozpoznanych linii (sprawdź format kodów)."
            messages.success(request, msg)
            return redirect("twin:warehouse_model_coords", pk=wm.pk)
    else:
        form = WarehouseModelForm()
    return render(request, "twin/warehouse_model/upload.html", {"form": form})

def _create_from_geometry(request, form, text):
    """Plik geometrii (np. z rysunku hali): regały od razu z pozycją, kątem i wymiarami.
    Błąd w którymkolwiek wierszu = nic nie zapisujemy (model nie powstaje „w połowie")."""
    racks, errors = parse_geometry_csv(text)
    if errors or not racks:
        for err in (errors or ["Plik nie zawiera żadnego regału."])[:10]:
            messages.error(request, err)
        return render(request, "twin/warehouse_model/upload.html", {"form": form})
    width, depth = floor_size(racks, rack_corners)
    with transaction.atomic():
        wm = form.save(commit=False)
        wm.floor_width_m = max(wm.floor_width_m or 0, width)
        wm.floor_depth_m = max(wm.floor_depth_m or 0, depth)
        wm.save()
        WarehouseModelRack.objects.bulk_create([WarehouseModelRack(model=wm, **r) for r in racks])
    messages.success(request, f"Wczytano {len(racks)} regałów z pozycjami — hala "
                              f"{wm.floor_width_m:g} × {wm.floor_depth_m:g} m.")
    return redirect("twin:warehouse_model_view", pk=wm.pk)


def _parse_pasted_codes(text):
    """Wklejone adresy → ({(zone, rack): {bays:set, levels:int}}, skipped).
    Toleruje kolumny po przecinku/tabie (bierze pierwszą, jak upload) i małe litery."""
    rack_map, skipped = {}, 0
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        code = line.replace("\t", ",").split(",")[0].strip().upper()
        parsed = _parse_location_code(code)
        if not parsed:
            if code:
                skipped += 1        # policz nierozpoznane — inaczej cicha utrata danych
            continue
        zone, rack, bay, lvl, lvl_num = parsed
        data = rack_map.setdefault((zone, rack), {"bays": set(), "levels": 0})
        data["bays"].add(bay)
        data["levels"] = max(data["levels"], lvl_num)
    return rack_map, skipped


@_md_role
def warehouse_model_paste(request, pk):
    """Wklej adresy jednej alejki/regału (zamiast pliku) i ustaw je w linii na planie:
    poziomo wzdłuż X (0°) albo pionowo wzdłuż Y (90°). Scalanie jest BEZSTRATNE —
    n_bays/n_levels istniejącego regału tylko rosną, nigdy nie maleją."""
    wm = get_object_or_404(WarehouseModel, pk=pk)
    ctx = {"wm": wm, "codes": "", "orientation": "horizontal",
           "start_x": 0, "start_y": 0, "keep_existing": False}
    if request.method != "POST":
        return render(request, "twin/warehouse_model/paste.html", ctx)

    codes_text = request.POST.get("codes") or ""
    orientation = "vertical" if request.POST.get("orientation") == "vertical" else "horizontal"
    keep_existing = bool(request.POST.get("keep_existing"))

    def _f(name):
        try:
            return float(request.POST.get(name) or 0)
        except (TypeError, ValueError):
            return 0.0
    start_x, start_y = _f("start_x"), _f("start_y")
    ctx.update({"codes": codes_text, "orientation": orientation, "start_x": start_x,
                "start_y": start_y, "keep_existing": keep_existing})

    rack_map, skipped = _parse_pasted_codes(codes_text)
    if not rack_map:
        messages.error(request, "Nie rozpoznano żadnego adresu — sprawdź format (np. B0-01-300A).")
        return render(request, "twin/warehouse_model/paste.html", ctx)

    from django.db import transaction
    angle = 90.0 if orientation == "vertical" else 0.0
    added = updated = repositioned = 0
    cursor = start_y if orientation == "vertical" else start_x
    with transaction.atomic():
        existing = {(r.zone, r.rack_id): r for r in wm.racks.select_for_update()}
        for (zone, rack_id), data in sorted(rack_map.items()):
            rack = existing.get((zone, rack_id))
            is_new = rack is None
            if is_new:
                rack = WarehouseModelRack(model=wm, zone=zone, rack_id=rack_id,
                                          n_bays=len(data["bays"]), n_levels=data["levels"])
                added += 1
            else:
                # Scalanie bezstratne: nigdy nie zmniejszaj już opisanego regału.
                rack.n_bays = max(rack.n_bays or 0, len(data["bays"]))
                rack.n_levels = max(rack.n_levels or 0, data["levels"])
                updated += 1
            place = is_new or not keep_existing
            if place:
                rack.angle_deg = angle
                if orientation == "vertical":
                    rack.x_m, rack.y_m = start_x, cursor
                else:
                    rack.x_m, rack.y_m = cursor, start_y
                if not is_new:
                    repositioned += 1
            rack.save()
            if place:
                cursor += rack.width_m       # kursor przesuwamy o realną szerokość regału

    msg = (f"Rozpoznano {len(rack_map)} regałów: dodano {added}, zaktualizowano {updated}"
           f"{f' (w tym przesunięto {repositioned})' if repositioned else ''}.")
    if skipped:
        msg += f" Pominięto {skipped} nierozpoznanych linii."
    messages.success(request, msg)
    limit = wm.floor_depth_m if orientation == "vertical" else wm.floor_width_m
    if limit and cursor > limit:
        messages.warning(request, f"Linia regałów ({cursor:.1f} m) wychodzi poza obrys hali "
                                  f"({limit} m) — popraw pozycje w edytorze.")
    return redirect("twin:warehouse_model_coords", pk=wm.pk)


@_md_role
def warehouse_model_coords(request, pk):
    from django.db import transaction
    wm = get_object_or_404(WarehouseModel, pk=pk)
    racks = wm.racks.order_by("zone", "rack_id")
    templates = list(BayTemplate.objects.all())
    if request.method == "POST":
        tpl_ids = {t.pk for t in templates}
        to_update, bad_numbers = [], []
        for rack in racks:
            prefix = f"rack_{rack.pk}_"
            try:
                rack.x_m = float(request.POST.get(prefix + "x_m") or 0)
                rack.y_m = float(request.POST.get(prefix + "y_m") or 0)
                rack.angle_deg = float(request.POST.get(prefix + "angle_deg") or 0)
                # max(1, ...) — jawne "0"/wartość ujemna daje zdegenerowaną geometrię (NaN/znika
                # w renderze three.js). `or default` chroni tylko puste. Jak w warehouse_rack_generator.
                rack.bay_width_cm = max(1, int(request.POST.get(prefix + "bay_width_cm") or 100))
                rack.depth_cm = max(1, int(request.POST.get(prefix + "depth_cm") or 80))
                rack.level_height_cm = max(1, int(request.POST.get(prefix + "level_height_cm") or 200))
            except (ValueError, TypeError):
                continue
            # Reguła adresu (edytor układu cz. 1) — tylko gdy formularz ją przysłał (stare
            # formularze/skrypty bez tych pól nie kasują szablonu ani numeracji).
            if prefix + "bay_numbers" in request.POST:
                tpl = request.POST.get(prefix + "template") or ""
                rack.template_id = int(tpl) if tpl.isdigit() and int(tpl) in tpl_ids else None
                rack.reverse = bool(request.POST.get(prefix + "reverse"))
                numbers = request.POST.get(prefix + "bay_numbers", "").strip()
                try:
                    parse_bay_numbers(numbers)
                    rack.bay_numbers = numbers
                except ValueError as exc:
                    bad_numbers.append(f"{rack}: {exc}")
            to_update.append(rack)
        if to_update:
            with transaction.atomic():
                WarehouseModelRack.objects.bulk_update(
                    to_update,
                    ["x_m", "y_m", "angle_deg", "bay_width_cm", "depth_cm", "level_height_cm",
                     "template", "bay_numbers", "reverse"],
                )
                touch_model(wm.pk)
        messages.success(request, "Współrzędne zapisane.")
        for msg in bad_numbers[:10]:
            messages.warning(request, f"Numeracja gniazd nie zmieniona — {msg}")
        return redirect("twin:warehouse_model_view", pk=wm.pk)
    return render(request, "twin/warehouse_model/coords.html", {"wm": wm, "racks": racks, "templates": templates})

def _rack_fill(wm, racks):
    """{(strefa, regał): %} ze stanu albo None (brak importu). Cache po (model, wersja, import stanów)."""
    from django.core.cache import cache

    from masterdata.services import current_stock_log
    from twin.blender_stock import load_master_levels, load_occupied_codes, rack_fill_pct
    log = current_stock_log()
    if log is None:
        return None
    key = "fill:" + cache_digest(wm.pk, wm.updated_at.timestamp(), log.pk, len(racks))
    hit = cache.get(key)
    if hit is None:
        dicts = [{"zone": r.zone, "rack_id": r.rack_id, "width": r.width_m, "n_bays": r.n_bays,
                  "n_levels": r.n_levels} for r in racks]
        hit = rack_fill_pct(dicts, load_occupied_codes() or (), load_master_levels())
        cache.set(key, hit, 3600)
    return hit


def model_scene_data(wm, racks=None):
    """Dane sceny 3D (createViewer): regały z kolorem strefy + elementy hali ze słupami. Wspólne dla widoku
    modelu i animacji dnia scenariusza (S4). Zwraca (racks_data, features_data, zone_color)."""
    racks = list(wm.racks.order_by("zone", "rack_id")) if racks is None else racks
    zones = sorted({r.zone for r in racks})
    zone_palette = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#f97316","#06b6d4","#ec4899","#14b8a6","#6b7280"]
    zone_color = {z: zone_palette[i % len(zone_palette)] for i, z in enumerate(zones)}
    fill = _rack_fill(wm, racks)
    racks_data = [
        {
            "id": r.pk, "zone": r.zone, "rack_id": r.rack_id,
            "x": r.x_m or 0, "y": r.y_m or 0,
            "width": r.width_m, "depth": r.depth_cm / 100,
            "angle": r.angle_deg,
            "n_levels": r.n_levels, "n_bays": r.n_bays,
            "level_h": r.level_height_cm / 100,
            "rack_class": rack_class({"equipment": r.equipment, "level_h": r.level_height_cm / 100}),
            "color": zone_color.get(r.zone, "#3b82f6"),
            # Wypełnienie regału [%] ze stanu (najnowszy import) — wskaźnik i tryb „Wypełnienie” w 3D;
            # None = brak importu stanów („brak danych”, nie zmyślona liczba).
            "fill_pct": fill.get((r.zone, r.rack_id)) if fill is not None else None,
        }
        for r in racks
    ]
    return racks_data, _features_data(wm), zone_color


@_planner
def warehouse_model_view(request, pk):
    wm = get_object_or_404(WarehouseModel, pk=pk)
    racks = list(wm.racks.order_by("zone", "rack_id"))
    racks_data, features_data, zone_color = model_scene_data(wm, racks)
    zones = sorted(zone_color)
    # Legenda typów elementów obecnych w modelu (unikalne kind, w kolejności definicji).
    _kinds = hall_feature_kinds()
    present_kinds = {f["kind"] for f in features_data}
    feature_legend = [
        {"label": _kinds[k], "color": HALL_FEATURE_COLORS[k]}
        for k in _kinds if k in present_kinds
    ]
    return render(request, "twin/warehouse_model/view.html", {
        "wm": wm,
        "racks": racks,                       # nagłówek „N regałów" (dotąd zawsze 0)
        # safe_json (nie json.dumps) — escapuje </>&, żeby wolny tekst z pola
        # (zone/rack_id/label regału) nie mógł wyjść z <script> (stored XSS).
        "racks_json": safe_json(racks_data),
        "features_json": safe_json(features_data),
        "site_json": safe_json(wm.site or {}),          # D1: teren działki w 3D (pusty = plac wokół hali)
        "feature_legend": feature_legend,
        "zone_color": zone_color,
        "zones": zones,
        "zone_legend": [{"zone": z, "color": zone_color[z]} for z in zones],
        "floor_w": wm.floor_width_m,
        "floor_d": wm.floor_depth_m,
        "clear_h": wm.clear_height_m or 0,     # wysokość ścian hali w 3D (0 = z wysokości regałów)
        "has_master": active_master() is not None,
        # Ruchy wózków: importy zadań EWM (?wt=<pk> z raportu importu = wybrany od razu).
        "flow_wt_batches": WarehouseTaskBatch.objects.filter(status="done", first_confirmed__isnull=False)[:12],
        "flow_wt_selected": request.GET.get("wt", ""),
    })

@_md_role
def warehouse_model_features(request, pk):
    """Edytowalna tabela elementów hali (dodawanie/edycja/usuwanie wierszy).
    Zapis/render przez współdzielone helpery (save_hall_features / hall_feature_dict)."""
    wm = get_object_or_404(WarehouseModel, pk=pk)
    if request.method == "POST":
        save_hall_features(request, "model", wm)
        messages.success(request, "Elementy hali zapisane.")
        return redirect("twin:warehouse_model_features", pk=wm.pk)

    return render(request, "twin/warehouse_model/features.html", {
        "wm": wm, "features": wm.features.all(),
        "kind_choices": WarehouseHallFeature.KIND_CHOICES,
        "dock_role_choices": WarehouseHallFeature.DOCK_ROLE_CHOICES,
        "feature_colors": HALL_FEATURE_COLORS,
        # Chrome parametryzowany (ten sam szablon dla modułu A — mapa 3D).
        "list_url": reverse("twin:warehouse_model_list"),
        "list_label": "Modele magazynu",
        "back_url": reverse("twin:warehouse_model_view", args=[wm.pk]),
        "parent_name": wm.name,
        "meta_line": f"hala {wm.floor_width_m}×{wm.floor_depth_m} m",
    })


def _features_data(wm):
    """Elementy hali → lista dictów do renderu (współdzielony hall_feature_dict) + słupy z siatki."""
    return [hall_feature_dict(f) for f in wm.features.all()] + model_columns(wm)


@_md_role
def warehouse_model_delete(request, pk):
    wm = get_object_or_404(WarehouseModel, pk=pk)
    if request.method == "POST":
        audit.record(request, AuditEvent.DELETE, wm, object_type="hala")
        wm.delete()
        messages.success(request, "Model magazynu usunięty.")
        return redirect("twin:warehouse_model_list")
    from core.deletion import confirm, hall_effects
    removed, detached = hall_effects(wm)
    return confirm(request, title="Usuń model magazynu", name=wm.name, removed=removed, detached=detached,
                   cancel_url=reverse("twin:warehouse_model_view", args=[wm.pk]), confirm_label="Tak, usuń model")

__all__ = [
    'warehouse_model_list',
    'warehouse_model_upload',
    'warehouse_model_paste',
    'warehouse_model_features',
    'warehouse_model_coords',
    'warehouse_model_view',
    'warehouse_model_delete',
]
