"""Kody lokalizacji magazynu — wspólna konwencja mapy 3D / eksportu SAP.

Litera na końcu kodu EWM = poziom (i półka/część) w jednym stosie — reguły w
ui.views.core.ewm_levels (B/C/D = półki poz. 1, X/G/H/T = 2, Y/U = 3, Z/V = 4, W = 5;
schemat blokowy A<cyfry>: A–E = 1–5). Legacy litery J/K/L/M/N/O = kolumna w boku; obsługuje też
4-członowy format generatora (B0-01-100-2X, litera = kolumna, poziom jawny).
"""


def parse_code(code):
    """Kod → (zone, rack_id, bay, col_idx, level) albo None."""
    from twin.shared import _parse_loc_code

    parsed = _parse_loc_code((code or "").strip().upper())
    if not parsed:
        return None
    aisle, stack, _col_code, col_idx, level = parsed
    zone, _, rack_id = aisle.partition("-")
    if not rack_id or not stack.isdigit():
        return None
    return zone, rack_id, stack, col_idx, level

