# Edycja wariantu hali (plan 2026-10-02, etap 4): kopia modelu jako wariant + operacje na całych
# strefach regałów (przesunięcie, gniazda, poziomy, usunięcie) z kontrolą kolizji.
from django.core.files.base import ContentFile

from twin.shared import (
    _md_role, get_object_or_404, messages, redirect, render, require_POST, transaction,
    WarehouseHallFeature, WarehouseModel, WarehouseModelRack,
)
from twin.blender_scene import model_racks
from twin.model_edit import apply_zone_edit, collisions, fit_floor, zone_summary

__all__ = ["warehouse_model_copy", "warehouse_model_zones"]

RACK_COPY_FIELDS = ("zone", "rack_id", "n_bays", "n_levels", "bay_width_cm", "depth_cm", "level_height_cm",
                    "x_m", "y_m", "angle_deg", "template_id", "bay_numbers", "reverse", "equipment", "equipment_model_id")
MODEL_COPY_FIELDS = ("notes", "floor_width_m", "floor_depth_m", "clear_height_m", "columns", "underlay_meta", "site")
FEATURE_COPY_FIELDS = ("kind", "label", "zone_code", "x_m", "y_m", "width_m", "depth_m", "angle_deg",
                       "color_hex", "notes")


@require_POST
@_md_role
def warehouse_model_copy(request, pk):
    """Kopia modelu (hala ze słupami i podkładem, regały, elementy hali) — „przyszły layout” do przeróbek
    w edytorze bez ruszania oryginału. Wyjątki adresów (LocationOverride) nie są kopiowane: to nowa hala,
    nie adresy EWM. Podkład dostaje własny plik (usunięcie go w kopii nie kasuje pliku oryginału)."""
    src = get_object_or_404(WarehouseModel, pk=pk)
    with transaction.atomic():
        wm = WarehouseModel.objects.create(name=f"{src.name} — przyszły layout"[:200],
                                           **{f: getattr(src, f) for f in MODEL_COPY_FIELDS})
        if src.underlay:
            with src.underlay.open("rb") as fh:
                wm.underlay.save(f"podklad_{wm.pk}.{src.underlay.name.rsplit('.', 1)[-1]}", ContentFile(fh.read()))
        WarehouseModelRack.objects.bulk_create([
            WarehouseModelRack(model=wm, **{f: getattr(r, f) for f in RACK_COPY_FIELDS}) for r in src.racks.all()])
        WarehouseHallFeature.objects.bulk_create([
            WarehouseHallFeature(model=wm, **{f: getattr(x, f) for f in FEATURE_COPY_FIELDS})
            for x in src.features.all()])
    messages.success(request, f"Utworzono „{wm.name}” — przebuduj go w edytorze, oryginał zostaje bez zmian.")
    return redirect("twin:warehouse_layout_editor", pk=wm.pk)


def _num(raw, cast, lo, hi):
    try:
        v = cast(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


@_md_role
def warehouse_model_zones(request, pk):
    wm = get_object_or_404(WarehouseModel, pk=pk)
    racks = model_racks(wm)
    zones = zone_summary(racks)
    if request.method == "POST":
        P, deleted = request.POST, set()
        for z in zones:
            key = z["zone"]
            if P.get(f"del_{key}"):
                deleted.add(key)
                continue
            apply_zone_edit(racks, key, dx=_num(P.get(f"dx_{key}"), float, -500, 500) or 0.0,
                            dy=_num(P.get(f"dy_{key}"), float, -500, 500) or 0.0,
                            n_bays=_num(P.get(f"bays_{key}"), int, 1, 500),
                            n_levels=_num(P.get(f"levels_{key}"), int, 1, 30))
        kept = [r for r in racks if r["zone"] not in deleted]
        if any(r["x"] < 0 or r["y"] < 0 for r in kept):
            messages.error(request, "Przesunięcie wypycha regały poza halę (ujemne X/Y) — nic nie zapisano.")
            # US-021: formularz wraca z wpisanymi wartościami, żeby poprawić przesunięcie zamiast wpisywać wszystko
            typed = [{**z, "dx": P.get(f"dx_{z['zone']}", "0"), "dy": P.get(f"dy_{z['zone']}", "0"),
                      "n_bays": P.get(f"bays_{z['zone']}", z["n_bays"]),
                      "n_levels": P.get(f"levels_{z['zone']}", z["n_levels"]),
                      "delete": bool(P.get(f"del_{z['zone']}"))} for z in zones]
            return render(request, "twin/warehouse_model/zones.html", {
                "wm": wm, "zones": typed, "floor_w": P.get("floor_w", ""), "floor_d": P.get("floor_d", "")},
                status=400)
        width, depth = fit_floor(kept, _num(P.get("floor_w"), float, 1, 5000) or wm.floor_width_m,
                                 _num(P.get("floor_d"), float, 1, 5000) or wm.floor_depth_m)
        by_pk = {r["id"]: r for r in kept}
        with transaction.atomic():
            objs = list(wm.racks.filter(pk__in=by_pk))
            for o in objs:
                r = by_pk[o.pk]
                o.x_m, o.y_m, o.n_bays, o.n_levels = r["x"], r["y"], r["n_bays"], r["n_levels"]
            WarehouseModelRack.objects.bulk_update(objs, ["x_m", "y_m", "n_bays", "n_levels"])
            wm.racks.filter(zone__in=deleted).delete()
            wm.floor_width_m, wm.floor_depth_m = width, depth
            wm.save(update_fields=["floor_width_m", "floor_depth_m", "updated_at"])
        hits = collisions(kept)
        messages.success(request, f"Zapisano wariant: hala {width:g} × {depth:g} m"
                                  + (f", usunięte strefy: {', '.join(sorted(deleted))}" if deleted else "") + ".")
        if hits:
            messages.warning(request, f"{len(hits)} kolizji regałów (np. {hits[0][0]} ↔ {hits[0][1]}) — popraw "
                                      "przesunięcie albo długość rzędów.")
        return redirect("twin:warehouse_model_view", pk=wm.pk)
    return render(request, "twin/warehouse_model/zones.html", {"wm": wm, "zones": zones})
