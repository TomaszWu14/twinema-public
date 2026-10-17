"""Kody lokalizacji magazynu — wspólna konwencja mapy 3D / eksportu SAP.

Litera na końcu kodu EWM = poziom (i półka/część) w jednym stosie — reguły w
twin.ewm_levels (A–H = poziomy 1–8, P/Q/R = półki poz. 1, S/T = części poz. 2).
Legacy litery J/K/L/M/N/O = kolumna w boku; obsługuje też
4-członowy format generatora (Z1-01-100-2X, litera = kolumna, poziom jawny).
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

