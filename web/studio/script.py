"""Scenariusz prezentacji (czysty Python — bez Django i bez sieci).

  • `kpi_facts` — z KPI modelu hali robi listę zdań z ZAGREGOWANYMI liczbami. Tylko to (bez nazw
    modelu, materiałów, lokalizacji) wolno wysłać do modelu językowego.
  • `template_script` — szkic bez AI: te same fakty ułożone w kwestie pod presety kamery.
  • `clean_draft` — walidacja szkicu (z AI albo z pliku): znane presety, niepuste kwestie, limity.
"""
import re

PRESETS = ("przelot", "orbita", "przejazd", "plan", "ogolny")
MIN_SHOTS, MAX_SHOTS = 3, 12
MAX_SHOT_CHARS = 600
TARGET_WORDS = (150, 260)       # napisy czyta się wolniej niż słucha lektora: ≈ 1,5–2,5 min filmu


def _num(x, digits=0):
    """Liczba po polsku: spacja tysięcy, przecinek dziesiętny."""
    s = f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s


def _get(kpi, dotted):
    for part in dotted.split("."):
        kpi = kpi.get(part) if isinstance(kpi, dict) else None
    return kpi


def kpi_facts(kpi):
    """Zdania z liczbami wariantu. Brak wartości → zdanie pominięte (nie zgadujemy)."""
    out = []
    if (fa := _get(kpi, "floor_area_m2")):
        out.append(f"Powierzchnia hali: {_num(fa)} m².")
    if (pp := _get(kpi, "pallet_positions")):
        line = f"Miejsca paletowe: {_num(pp)}"
        if (pm := _get(kpi, "positions_per_m2")):
            line += f" ({_num(pm, 2)} na m² hali)"
        out.append(line + ".")
    if (ba := _get(kpi, "built_area_m2")):
        out.append(f"Powierzchnia zabudowy regałami i sprzętem: {_num(ba)} m².")
    if (avg := _get(kpi, "travel.avg_m")) is not None:
        out.append(f"Średnia droga do miejsca paletowego: {_num(avg, 1)} m.")
    if (az := _get(kpi, "travel.a_zone_avg_m")) is not None:
        out.append(f"Średnia droga do strefy A (20 % najbliższych miejsc): {_num(az, 1)} m.")
    for k in (_get(kpi, "equipment") or {}).values():
        out.append(f"{k['label']}: {k['count']} szt., nominalnie {_num(k['throughput_h'])} na godzinę.")
    issues = _get(kpi, "aisle_issue_count")
    if issues is not None:
        out.append("Alejki bez naruszeń szerokości i kolizji." if issues == 0
                   else f"Naruszenia alejek do poprawy: {issues}.")
    return out


def template_script(kpi):
    """Szkic bez AI — działa zawsze, także bez klucza API. Do edycji przez projektanta."""
    f = kpi_facts(kpi)
    capacity = " ".join(x for x in f if x.startswith(("Powierzchnia hali", "Miejsca paletowe")))
    travel = " ".join(x for x in f if x.startswith("Średnia droga"))
    rest = " ".join(x for x in f if not x.startswith(("Powierzchnia hali", "Miejsca paletowe", "Średnia droga")))
    return [
        {"preset": "przelot", "text": "Oto projekt nowego centrum dystrybucyjnego — od pustej hali "
                                      "do układu gotowego do symulacji i budowy."},
        {"preset": "plan", "text": capacity or "Plan hali pokazuje układ regałów i stref."},
        {"preset": "przejazd", "text": travel or "Alejki prowadzą wózki najkrótszą drogą od doków do regałów."},
        {"preset": "orbita", "text": rest or "Sprzęt dobrano do zakładanego wolumenu zadań."},
        {"preset": "ogolny", "text": "Model jest gotowy do porównania wariantów i decyzji o inwestycji."},
    ]


def clean_draft(shots):
    """[{preset, text}] → poprawione kwestie. Nieznany preset → „ogólny”, pusta kwestia → pominięta,
    za długa → przycięta na granicy zdania. Zwraca (shots, ostrzeżenia)."""
    out, warnings = [], []
    for i, s in enumerate(shots if isinstance(shots, list) else []):
        text = re.sub(r"\s+", " ", str((s or {}).get("text") or "")).strip()
        if not text:
            warnings.append(f"Kwestia {i + 1} była pusta — pominięta.")
            continue
        if len(text) > MAX_SHOT_CHARS:
            cut = text[:MAX_SHOT_CHARS]
            text = cut[:cut.rfind(". ") + 1] or cut
            warnings.append(f"Kwestia {i + 1} była za długa — przycięta.")
        preset = (s or {}).get("preset")
        if preset not in PRESETS:
            warnings.append(f"Kwestia {i + 1}: nieznane ujęcie „{preset}” → widok ogólny.")
            preset = "ogolny"
        out.append({"preset": preset, "text": text})
    if len(out) > MAX_SHOTS:
        warnings.append(f"Za dużo kwestii ({len(out)}) — zostawiono {MAX_SHOTS}.")
        out = out[:MAX_SHOTS]
    return out, warnings

