"""Wspólne importy i pomocnicze widoków bliźniaka — odpowiednik jądra widoków ze źródła
(PROVENANCE.md), odchudzony do tego, czego używa moduł: skróty Django, dekoratory ról,
bezpieczny JSON do <script>, parser kodu lokalizacji, elementy hali."""
import hashlib
import json
import re

from django.contrib import messages  # noqa: F401
from django.db import transaction  # noqa: F401
from django.db.models import Count  # noqa: F401
from django.http import JsonResponse  # noqa: F401
from django.shortcuts import get_object_or_404, redirect, render  # noqa: F401
from django.template.loader import render_to_string  # noqa: F401
from django.views.decorators.http import require_POST  # noqa: F401

from core.roles import any_role, designer

from .ewm_levels import letter_level, letter_slot
from .models import (  # noqa: F401
    WarehouseDesignVariant, WarehouseHallFeature, WarehouseLocationMaster, WarehouseLocationMasterBatch,
    WarehouseModel, WarehouseModelRack, WarehouseRackType,
)

# Dekoratory pod nazwami ze źródła: zapis = Projektant, odczyt = każda rola.
_md_role = designer
_planner = any_role


def cache_digest(*parts):
    """Klucz cache z dowolnych parametrów (bez spacji/dwukropków — bezpieczny dla każdego backendu)."""
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def safe_json(obj):
    """JSON bezpieczny do osadzenia w <script> przez |safe (escapuje <, >, & i separatory JS)."""
    from django.core.serializers.json import DjangoJSONEncoder
    s = json.dumps(obj, cls=DjangoJSONEncoder)
    s = s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


# Litera → (kolumna, poziom) dla liter spoza słownika poziomów (stary format generatora).
_COL_CODE_MAP = {
    'A': (0, 1), 'B': (1, 1), 'C': (2, 1), 'D': (3, 1),
    'S': (0, 1), 'T': (1, 1), 'U': (2, 1), 'V': (3, 1),
    'G': (0, 1), 'H': (1, 1),
    'X': (0, 2), 'J': (1, 2), 'K': (2, 2),
    'Y': (0, 3), 'L': (1, 3), 'M': (2, 3),
    'Z': (0, 4), 'N': (1, 4), 'O': (2, 4),
}


def _parse_location_code(code: str):
    """Z1-01-300A → (zone, rack, bay, level_letter, level_num)."""
    m = re.match(r'^([A-Z]\d+)-(\d+)-(\d+)([A-Z])$', code.strip())
    if not m:
        return None
    zone, rack, bay, lvl = m.group(1), m.group(2), m.group(3), m.group(4)
    level_num = letter_level(zone, lvl, default=ord(lvl) - ord('A') + 1)
    return zone, rack, bay, lvl, level_num


def _parse_loc_code(code):
    """Z1-01-100A → (aisle, stack, col_code, col_idx, level); aisle zawiera strefę ('Z1-01')."""
    parts = code.split('-')
    # Format 4-częściowy: zone-aisle-stack-{level}{col}, np. Z1-01-100-2X — przed 3-częściowym.
    if len(parts) >= 4 and parts[3] and parts[3][-1].isalpha() and parts[3][:-1].isdigit():
        zone = parts[0]
        col_code = parts[3][-1].upper()
        col_idx, _lvl = _COL_CODE_MAP.get(col_code, (0, 1))
        return f"{zone}-{parts[1]}", parts[2], col_code, col_idx, int(parts[3][:-1])
    if len(parts) >= 3:
        zone = parts[0]
        aisle = f"{zone}-{parts[1]}"
        stack_raw = parts[2]
        if stack_raw and stack_raw[-1].isalpha():
            col_code, stack = stack_raw[-1].upper(), stack_raw[:-1]
        else:
            col_code, stack = 'A', stack_raw
        slot = letter_slot(zone, col_code)
        col_idx, level = (0, slot.level) if slot else _COL_CODE_MAP.get(col_code, (0, 1))
        return aisle, stack, col_code, col_idx, level
    return None


# ── Elementy hali ─────────────────────────────────────────────────────────────
# G2: spokojna paleta (przygaszone odcienie na szarej posadzce); nasycony zostaje tylko kolor bezpieczeństwa
# (droga pożarowa). Strefy specjalne = te same kolory w trybie „Strefy” widoku 3D (scene-data.rackTint).
HALL_FEATURE_COLORS = {
    "dock": "#64748b", "gate": "#4b86b4", "corridor": "#94a3b8",
    "block_zone": "#7d7a99", "staging": "#c9a54a", "returns": "#a8806b", "leader": "#5f9a72",
    "station": "#a99572", "other": "#6b7280",
    "fire_route": "#dc2626", "charging": "#3e9a90", "walkway": "#7fb28a", "truckway": "#c9ad55",
    "zone_temp": "#4f9ccc", "zone_adr": "#d07a3a", "zone_oversize": "#8f8a84", "zone_value": "#8d72b0",
}


FORM_DEFAULT_COLOR = "#94a3b8"   # wartość pola koloru w formularzu, gdy element nie ma własnego


def own_color(kind, posted):
    """Kolor do zapisu: tylko własny wybór użytkownika. Domyślny kolor rodzaju (albo domyślna wartość pola
    formularza) → "" — wtedy element idzie za paletą HALL_FEATURE_COLORS i jej zmiany (G2)."""
    c = (posted or "").strip().lower()[:7]
    return "" if c in (HALL_FEATURE_COLORS.get(kind), FORM_DEFAULT_COLOR) else c


def hall_feature_kinds():
    return dict(WarehouseHallFeature.KIND_CHOICES)


def hall_feature_dict(f):
    """Element hali → dict do renderu (kolor rozwiązany, etykieta z rodzaju)."""
    kinds = hall_feature_kinds()
    return {
        "id": f.pk, "kind": f.kind,
        "kind_label": kinds.get(f.kind, f.kind),
        "label": f.label or kinds.get(f.kind, ""),
        "x": f.x_m, "y": f.y_m, "width": f.width_m, "depth": f.depth_m,
        "angle": f.angle_deg,
        "color": (f.color_hex or HALL_FEATURE_COLORS.get(f.kind, "#6b7280")),
        "zone_code": f.zone_code,
        "dock_role": getattr(f, "dock_role", "") or "",
    }


def model_columns(wm):
    """Słupy hali jako elementy „column” (format hall_feature_dict + `height`) dla widoku 3D i Blendera."""
    from .layout import column_list

    h = wm.clear_height_m or 8.0
    return [{"id": None, "kind": "column", "kind_label": "Słup", "label": "", "zone_code": "",
             "x": c["x"] - c["size"] / 2, "y": c["y"] - c["size"] / 2, "width": c["size"], "depth": c["size"],
             "angle": 0.0, "color": "#475569", "height": h}
            for c in column_list(wm.columns, {"width": wm.floor_width_m, "depth": wm.floor_depth_m})]


def save_hall_features(request, owner_field, owner_obj):
    """Zapis edytowalnej tabeli elementów hali z równoległych list POST + deleted_ids."""
    valid = dict(WarehouseHallFeature.KIND_CHOICES)
    P = request.POST
    row_ids = P.getlist("row_id")
    kinds = P.getlist("kind")
    labels, zone_codes = P.getlist("label"), P.getlist("zone_code")
    xs, ys = P.getlist("x_m"), P.getlist("y_m")
    ws, ds = P.getlist("width_m"), P.getlist("depth_m")
    angles, colors, notes = P.getlist("angle_deg"), P.getlist("color_hex"), P.getlist("notes")
    roles, valid_roles = P.getlist("dock_role"), dict(WarehouseHallFeature.DOCK_ROLE_CHOICES)
    deleted = [d for d in (P.get("deleted_ids") or "").split(",") if d.strip().isdigit()]

    def _f(lst, i, default=0.0):
        try:
            return float(lst[i]) if i < len(lst) and lst[i] != "" else default
        except (ValueError, TypeError):
            return default

    features_qs = owner_obj.features
    with transaction.atomic():
        if deleted:
            features_qs.filter(pk__in=deleted).delete()
        existing = {f.pk: f for f in features_qs.all()}
        for i in range(len(kinds)):
            rid = row_ids[i] if i < len(row_ids) else ""
            kind = kinds[i] if kinds[i] in valid else "other"
            feat = existing.get(int(rid)) if rid.isdigit() else None
            if feat is None:
                feat = WarehouseHallFeature(**{owner_field: owner_obj})
            feat.kind = kind
            feat.label = (labels[i] if i < len(labels) else "")[:100]
            feat.zone_code = (zone_codes[i] if i < len(zone_codes) else "").strip().upper()[:20]
            feat.x_m, feat.y_m = _f(xs, i), _f(ys, i)
            feat.width_m, feat.depth_m = _f(ws, i, 2), _f(ds, i, 2)
            feat.angle_deg = _f(angles, i)
            feat.color_hex = own_color(kind, colors[i] if i < len(colors) else "")
            feat.notes = (notes[i] if i < len(notes) else "")[:200]
            if i < len(roles):                  # stary formularz bez kolumny roli — nie nadpisuj
                feat.dock_role = roles[i] if roles[i] in valid_roles and kind in ("dock", "gate") else ""
            feat.save()


def operator_key():
    """Klucz pseudonimizacji loginów operatorów (US-012) — pochodna klucza aplikacji, nigdy w bazie ani w logach.
    Zmiana DJANGO_SECRET_KEY zmienia pseudonimy nowych importów (stare partie zostają spójne w sobie)."""
    from django.conf import settings
    return hashlib.sha256(b"twinema.operator-pseudonym:" + settings.SECRET_KEY.encode()).digest()
