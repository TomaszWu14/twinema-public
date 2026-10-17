# Scena przepływów modelu magazynu: eksport do Blendera (tools/blender/) oraz ten sam
# JSON dla animacji w aplikacji (odtwarzacz three.js w widoku 3D modelu).


from django.core.cache import cache

from core.roles import GROUP_ADMIN, GROUP_DESIGNER, has_role
from twin.shared import (
    _planner, cache_digest, get_object_or_404, hall_feature_dict, JsonResponse, WarehouseModel,
)
from twin.blender_scene import build_scene_for_model, model_floor, model_racks
from twin.blender_tasks import MAX_HOURS, default_start, load_window, parse_start
from twin.models_tasks import WarehouseTaskBatch

# Limity: A* ~20 ms na trasę (hala 120×80 m) — 10 pickerów × 25 pobrań ≈ 6 s liczenia,
# a widok jest synchroniczny (jeden worker gunicorna na czas liczenia).
MAX_FORKLIFTS, MAX_PICKERS, MAX_PICKS = 10, 10, 25
# Dane źródłowe (stany, partie, HU, kody lokalizacji z mastera) — rola Podgląd ich nie widzi (ZALOZENIA #25).
SOURCE_PALLET_KEYS = ("sku", "name", "lot", "hu", "qty", "unit", "expiry", "days_to_expiry")
SIM_TRACE_TTL = 3600
VIEWER_SCENE_TTL = 600     # scena dla Podglądu/gościa: parametry domyślne, liczona raz na 10 min na halę


def _full_access(request):
    """Projektant/Administratorzy albo wywołanie wewnętrzne (worker renderów, studio — bez `user`)."""
    user = getattr(request, "user", None)
    return user is None or has_role(user, GROUP_ADMIN, GROUP_DESIGNER)


def _for_viewer(scene):
    """Scena bez danych źródłowych: palety jako anonimowe bryły (stan, klasa ABC, liczba pobrań zostają)."""
    for p in scene.get("pallets") or []:
        for k in SOURCE_PALLET_KEYS:
            p.pop(k, None)
        p["code"] = ""
    for it in scene.get("items") or []:
        it["sku"] = ""
    for key in ("batch", "tasks_batch", "snapshot"):
        (scene.get("source") or {}).pop(key, None)
    (scene.get("info") or {}).pop("batch", None)
    ((scene.get("source") or {}).get("simulation") or {}).pop("batch", None)   # nazwa importu zadań (przegląd SEC)
    return scene


def _clamped(raw, default, lo, hi):
    try:
        return min(hi, max(lo, int(raw)))
    except (TypeError, ValueError):
        return default


def _clamped_float(raw, default, lo, hi):
    try:
        return min(hi, max(lo, float(raw)))
    except (TypeError, ValueError):
        return default


def _wt_window(request):
    """?wt=<id>|latest — wózki z importu zadań EWM w oknie ?wt_from (czas lokalny,
    domyślnie 1. godzina partii) + ?wt_hours (0,25–24, domyślnie 1) z kompresją ?wt_scale
    (1–120 — skraca tylko postoje między zadaniami). Inna wartość/brak → wózki demo."""
    param = (request.GET.get("wt") or "").strip()
    done = WarehouseTaskBatch.objects.filter(status="done")
    if param == "latest":
        batch = done.first()
    elif param.isdigit():
        batch = get_object_or_404(done, pk=int(param))
    else:
        return None
    if batch is None:
        return None
    start = parse_start(request.GET.get("wt_from")) or default_start(batch)
    if start is None:                                     # partia bez potwierdzonych zadań
        return None
    return load_window(batch, start, hours=_clamped_float(request.GET.get("wt_hours"), 1.0, 0.25, MAX_HOURS),
                       scale=_clamped_float(request.GET.get("wt_scale"), 1.0, 1.0, 120.0))


def _sim_scene(request, wm):
    """?sim=<id importu WT>&sim_h=<godzina 5–20>&p=&mult=&agv=&kombi=&ept= — godzina z symulacji
    dnia projektowego na tym modelu (etap 3b). Brak ?sim → None (zwykła scena)."""
    from twin.design_sim import DAY_END_H, DAY_START_H
    from twin.design_sim_scene import build_sim_scene
    from twin.views.warehouse_design_sim import design_day, run_simulation, sim_params

    param = (request.GET.get("sim") or "").strip()
    if not param.isdigit():
        return None
    batch = get_object_or_404(WarehouseTaskBatch, pk=int(param), status="done")
    prm = sim_params(request.GET)
    hour = _clamped(request.GET.get("sim_h"), DAY_START_H + 3, DAY_START_H, DAY_END_H - 1)
    racks = model_racks(wm)
    features = [hall_feature_dict(f) for f in wm.features.all()]
    model = {"id": wm.pk, "name": wm.name}
    day = design_day(batch, prm["p"])
    # cały dzień liczony raz na (partia, model, parametry) — zmiana godziny tylko wycina fragment śladu
    key = "sim-trace:" + cache_digest(batch.pk, wm.pk, wm.updated_at.timestamp(), day, prm)
    cached = cache.get(key) if day else None
    # Z-3 (decyzja PO): cały dzień liczy tylko Projektant; Podgląd i gość widzą ślad policzony wcześniej
    if day and cached is None and has_role(request.user, GROUP_ADMIN, GROUP_DESIGNER):
        trace = []
        cached = (trace, run_simulation(batch, wm, day, prm, trace=trace)[0] is not None)
        cache.set(key, cached, SIM_TRACE_TTL)
    trace, ok = cached or ([], False)
    if not ok:                    # brak dnia albo model bez VNA/półek → pusta scena + komunikat
        return build_sim_scene(model, model_floor(wm, racks), racks, features, [], hour)
    return build_sim_scene(model, model_floor(wm, racks), racks, features, trace, hour,
                           info={"batch": batch.name, "day": day.isoformat(), "p": prm["p"],
                                 "mult": prm["mult"], "fleet": prm["fleet"]})


def _scene_from_request(request, wm):
    """Scena „twinema.scene" wg parametrów URL (wspólne dla eksportu i animacji).

    Kompletacja = symulacja demo (import aktywności pickerów dojdzie z modułem Dane).
    ?pallets=0 — bez palet w lokalizacjach. ?forklifts=0–10 (demo), ?pickers=1–10, ?picks=1–25.
    ?wt=… — wózki z zadań EWM (patrz `_wt_window`)."""
    full = _full_access(request)
    scene = _sim_scene(request, wm)
    if scene is None and not full:
        # Z-3, przegląd SEC: Podgląd i gość nie zlecają liczenia tras (~6 s na żądanie) — parametry domyślne,
        # wynik z pamięci podręcznej na halę; inaczej pętla żądań z /demo/ zajęłaby wszystkie workery serwera
        with_pallets = request.GET.get("pallets") != "0"
        key = "viewer-scene:" + cache_digest(wm.pk, wm.updated_at.timestamp(), with_pallets)
        scene = cache.get(key)
        if scene is None:
            scene = _for_viewer(build_scene_for_model(wm, None, with_pallets=with_pallets))
            cache.set(key, scene, VIEWER_SCENE_TTL)
        return scene
    scene = scene or build_scene_for_model(
        wm, None,
        forklifts=_clamped(request.GET.get("forklifts"), 3, 0, MAX_FORKLIFTS),
        max_pickers=_clamped(request.GET.get("pickers"), 6, 1, MAX_PICKERS),
        max_picks=_clamped(request.GET.get("picks"), 12, 1, MAX_PICKS),
        with_pallets=request.GET.get("pallets") != "0", wt=_wt_window(request) if full else None)
    return scene if full else _for_viewer(scene)


@_planner
def warehouse_model_blender_json(request, pk):
    """Scena „twinema.scene" (JSON do pobrania) dla skryptu Blendera / Blender MCP."""
    wm = get_object_or_404(WarehouseModel, pk=pk)
    resp = JsonResponse(_scene_from_request(request, wm), json_dumps_params={"ensure_ascii": False})
    resp["Content-Disposition"] = f'attachment; filename="twinema_model_{wm.pk}_blender.json"'
    return resp


@_planner
def warehouse_model_flow_json(request, pk):
    """Ta sama scena dla animacji przepływów w aplikacji (fetch z widoku 3D modelu)."""
    wm = get_object_or_404(WarehouseModel, pk=pk)
    return JsonResponse(_scene_from_request(request, wm), json_dumps_params={"ensure_ascii": False})
