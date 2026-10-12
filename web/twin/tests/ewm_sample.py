"""Syntetyczna próbka mastera lokalizacji (hala B0) dla testów „Wykryj z EWM” i zgodności.

Trzy rzędy, dwa szablony gniazd, jedna nieregularność numeracji:
  07 — gniazda 10–48, 3 palety na belce, poziomy A X Y Z (A = 0020, reszta 0010),
  08 — jak 07, ale numeracja przeskakuje 48–49 (gniazda 10–47 i 50),
  48 — gniazda 10–45, półki B C D w poziomie 1 (0030) + X Y Z (0010).
"""

SAMPLE_N_BAYS = {"07": 39, "08": 39, "48": 36}
_ROWS = {
    "07": (list(range(10, 49)), {"A": "0020", "X": "0010", "Y": "0010", "Z": "0010"}),
    "08": (list(range(10, 48)) + [50], {"A": "0020", "X": "0010", "Y": "0010", "Z": "0010"}),
    "48": (list(range(10, 46)), {"B": "0030", "C": "0030", "D": "0030", "X": "0010", "Y": "0010", "Z": "0010"}),
}
SAMPLE_CODES = 39 * 3 * 4 + 39 * 3 * 4 + 36 * 3 * 6     # 1584 miejsc


def load_sample():
    """[(kod, typ EWM)] — kod B0-<rząd>-<gniazdo><pozycja palety><litera poziomu>."""
    return [(f"B0-{aisle}-{bay}{pos}{letter}", typ)
            for aisle, (bays, levels) in _ROWS.items()
            for bay in bays for pos in range(3) for letter, typ in levels.items()]
