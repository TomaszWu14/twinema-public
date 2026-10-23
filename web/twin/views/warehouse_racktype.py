# Auto-split from the former monolithic views.py. Feature views live in
# sibling modules; shared imports/constants/helpers stay in core.py.
import math

from twin.shared import (
    _md_role, _planner, get_object_or_404, messages, redirect, render,
    require_POST, WarehouseRackType, safe_json,
)


@_planner
def warehouse_rack_type_list(request):
    types = list(WarehouseRackType.objects.all())
    # Lista grupowana: najpierw regały (z wymiarami do 3D), potem strefy.
    return render(request, "twin/warehouse_map/rack_type_list.html", {
        "racks": [t for t in types if t.kind == "rack"],
        "zones": [t for t in types if t.kind != "rack"],
        "types": types,
    })

@_md_role
def warehouse_rack_type_form(request, pk=None):
    obj = get_object_or_404(WarehouseRackType, pk=pk) if pk else None

    if request.method == "POST":
        code  = request.POST.get("code", "").strip().upper()
        name  = request.POST.get("name", "").strip()
        if not code or not name:
            messages.error(request, "Kod i nazwa są wymagane.")
            return _form_again(request, obj)
        kind = request.POST.get("kind", "rack")
        if kind not in dict(WarehouseRackType.KIND):
            kind = "rack"
        description = (request.POST.get("description") or "").strip()[:200]

        # Parse per-level heights + weights from POST (level_N_height / level_N_weight)
        level_heights = {}
        level_weights = {}
        for lv in range(1, 9):
            raw = request.POST.get(f"level_{lv}_height", "").strip()
            if raw:
                try:
                    level_heights[str(lv)] = max(100, int(raw))
                except (ValueError, TypeError):
                    pass
            raw_w = request.POST.get(f"level_{lv}_weight", "").strip()
            if raw_w:
                try:
                    level_weights[str(lv)] = max(0, int(float(raw_w)))
                except (ValueError, TypeError, OverflowError):   # „inf” → OverflowError, nie 500
                    pass

        try:
            width_mm      = max(100, int(request.POST.get("width_mm", 800) or 800))
            manip_mm      = max(100, int(request.POST.get("manip_mm", 900) or 900))
            depth_mm      = max(100, int(request.POST.get("depth_mm", 1100) or 1100))
            max_weight_kg = float(request.POST.get("max_weight_kg", 1200) or 1200)
            max_volume_m3 = float(request.POST.get("max_volume_m3", 2.5) or 2.5)
            if not (math.isfinite(max_weight_kg) and math.isfinite(max_volume_m3)):
                raise ValueError("wartość musi być liczbą skończoną")      # „nan”/„inf” psują JSON widoku 3D
        except (ValueError, TypeError, OverflowError) as e:
            messages.error(request, f"Błąd wartości: {e}")
            return _form_again(request, obj)

        import re as _re
        raw_color = request.POST.get("color_hex", "").strip()
        if _re.fullmatch(r'#[0-9a-fA-F]{6}', raw_color):
            color_hex = raw_color
        else:
            color_hex = "#f59e0b"

        # Parse per-level column counts from POST (level_cols JSON textarea)
        import json as _json
        level_cols = {}
        raw_level_cols = request.POST.get("level_cols_json", "").strip()
        if raw_level_cols:
            try:
                parsed_lc = _json.loads(raw_level_cols)
                if isinstance(parsed_lc, dict):
                    for k, v in parsed_lc.items():
                        try:
                            nc = max(1, min(3, int(v)))
                            level_cols[str(k)] = nc
                        except (ValueError, TypeError, OverflowError):   # 1e999 → inf
                            pass
            except (_json.JSONDecodeError, ValueError):
                messages.error(request, "Nieprawidłowy format JSON dla kolumn per poziom.")
                return _form_again(request, obj)

        if obj:
            if WarehouseRackType.objects.filter(code=code).exclude(pk=obj.pk).exists():
                messages.error(request, f"Typ o kodzie «{code}» już istnieje.")
                return _form_again(request, obj)
            obj.code          = code
            obj.name          = name
            obj.kind          = kind
            obj.description   = description
            obj.width_mm      = width_mm
            obj.manip_mm      = manip_mm
            obj.depth_mm      = depth_mm
            obj.max_weight_kg = max_weight_kg
            obj.max_volume_m3 = max_volume_m3
            obj.level_heights = level_heights
            obj.level_cols    = level_cols
            obj.level_weights = level_weights
            obj.color_hex     = color_hex
            obj.save()
            messages.success(request, f"Typ «{code}» zaktualizowany.")
        else:
            if WarehouseRackType.objects.filter(code=code).exists():
                messages.error(request, f"Typ o kodzie «{code}» już istnieje.")
                return _form_again(request, obj)
            WarehouseRackType.objects.create(
                code=code, name=name, kind=kind, description=description,
                width_mm=width_mm, manip_mm=manip_mm, depth_mm=depth_mm,
                max_weight_kg=max_weight_kg, max_volume_m3=max_volume_m3,
                level_heights=level_heights, level_cols=level_cols,
                level_weights=level_weights, color_hex=color_hex,
            )
            messages.success(request, f"Typ «{code}» utworzony.")

        return redirect("twin:warehouse_rack_type_list")

    # GET: show form
    level_heights_json = safe_json(obj.level_heights) if obj and obj.level_heights else "{}"
    level_cols_json = safe_json(obj.level_cols) if obj and obj.level_cols else "{}"
    level_weights_json = safe_json(obj.level_weights) if obj and obj.level_weights else "{}"
    return render(request, "twin/warehouse_map/rack_type_form.html", {
        "obj": obj,
        "level_heights_json": level_heights_json,
        "level_cols_json": level_cols_json,
        "level_weights_json": level_weights_json,
    })

def _form_again(request, obj):
    """US-021: błąd walidacji → ten sam formularz z wpisanymi wartościami (zamiast powrotu do listy bez danych)."""
    post = request.POST
    draft = WarehouseRackType(pk=obj.pk if obj else None, code=post.get("code", "").strip().upper(),
                              name=post.get("name", "").strip(), kind=post.get("kind", "rack"),
                              description=(post.get("description") or "").strip()[:200],
                              color_hex=post.get("color_hex", "").strip())
    for f in ("width_mm", "manip_mm", "depth_mm", "max_weight_kg", "max_volume_m3"):
        setattr(draft, f, post.get(f, "").strip())               # surowy tekst — do poprawienia przez użytkownika
    heights = {str(lv): post[f"level_{lv}_height"].strip() for lv in range(1, 9)
               if post.get(f"level_{lv}_height", "").strip()}
    weights = {str(lv): post[f"level_{lv}_weight"].strip() for lv in range(1, 9)
               if post.get(f"level_{lv}_weight", "").strip()}
    draft.level_heights, draft.level_weights = heights, weights
    return render(request, "twin/warehouse_map/rack_type_form.html", {
        "obj": draft,
        "level_heights_json": safe_json(heights),
        "level_cols_json": safe_json(obj.level_cols if obj and obj.level_cols else {}),
        "level_cols_raw": post.get("level_cols_json", ""),
        "level_weights_json": safe_json(weights),
    }, status=400)


@_md_role
@require_POST
def warehouse_rack_type_delete(request, pk):
    obj = get_object_or_404(WarehouseRackType, pk=pk)
    code = obj.code
    obj.delete()
    messages.success(request, f"Typ «{code}» usunięty.")
    return redirect("twin:warehouse_rack_type_list")

__all__ = [
    'warehouse_rack_type_list',
    'warehouse_rack_type_form',
    'warehouse_rack_type_delete',
]
