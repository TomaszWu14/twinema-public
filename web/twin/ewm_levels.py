"""Litera kodu lokalizacji EWM → fizyczne miejsce w stosie (JEDNO źródło prawdy).

Kod EWM: ``{strefa}-{przejście}-{gniazdo:02}{pozycja}{litera}[-1|-2]``, np. ``Z1-07-300C-1``.
Litera NIE jest kolumną w boku — to poziom (i ewentualnie półka / część) w jednym stosie.
Konwencja adresowania przyjęta w projekcie — jedna dla wszystkich stref, od podłogi:

  • ``A``..``H`` = poziomy 1..8 (pełne miejsce paletowe),
  • ``P`` / ``Q`` / ``R`` = półki 1..3 JEDNA NAD DRUGĄ w otworze poziomu 1 (kompletacja; P najniżej),
  • ``S`` / ``T`` = dolna / górna część poziomu 2 podzielonego w pionie (zamiast pełnego ``B``),
  • końcówka ``-1``/``-2`` (np. ``P-1``, ``Q-2``) = lewa/prawa połówka (~40 cm) tego miejsca.

Poziom ZAWSZE wynika z litery, nie z kolumny poziomu w eksporcie (dla półek dzielonych
kolumna ta może zawierać kolejne numery zamiast poziomu). Nieznana litera (np. legacy J/K/L/M/N/O
generatora) → ``None``: konsument zachowuje swój dotychczasowy fallback.

Czysty Python (bez ORM) — testowalny bez bazy.
"""
from typing import NamedTuple


class LetterSlot(NamedTuple):
    """Fizyczne miejsce litery w stosie.

    level — poziom 1..8 (1 = dół / picking),
    shelf — 0 = całe miejsce poziomu; 1.. = półka/część od dołu w otworze poziomu
            (P=1, Q=2, R=3 w poziomie 1; S=1, T=2 w poziomie 2 przy podziale pionowym),
    side  — 0 = cała szerokość; 1 = lewa, 2 = prawa połówka (końcówka -1/-2; także S/T,
            gdyby podział poziomu 2 był poziomy — patrz SPLIT_VERTICAL).
    """
    level: int
    shelf: int
    side: int


# S/T dzielą miejsce poziomu 2 (każde ~1,1 m³ zamiast 2,2 m³). Przyjęty podział
# PIONOWY (S niżej, T wyżej). False = podział na lewą/prawą część (side 1/2).
SPLIT_VERTICAL = True

_LEVELS = {letter: n for n, letter in enumerate("ABCDEFGH", start=1)}
_SHELVES = {"P": 1, "Q": 2, "R": 3}          # półki w otworze poziomu 1
_SPLIT = {"S": 1, "T": 2}                    # części poziomu 2


def _split_letter(letter, half):
    """„P-1” → („P”, 1); „p” → („P”, half)."""
    s = (letter or "").strip().upper()
    base, _, suffix = s.partition("-")
    if suffix.isdigit():
        half = int(suffix)
    return base, int(half or 0)


def letter_slot(zone, letter, half=0):
    """(strefa, litera[, połówka 1/2]) → LetterSlot albo None dla nieznanej litery.

    ``letter`` może zawierać końcówkę połówki („P-1”) — wtedy nadpisuje ``half``. Strefa nie
    zmienia znaczenia litery (parametr zostaje dla zgodności wywołań)."""
    base, half = _split_letter(letter, half)
    side = half if half in (1, 2) else 0
    if len(base) != 1:
        return None
    if base in _LEVELS:
        return LetterSlot(_LEVELS[base], 0, side)
    if base in _SHELVES:
        return LetterSlot(1, _SHELVES[base], side)
    if base in _SPLIT:
        part = _SPLIT[base]
        return LetterSlot(2, part, side) if SPLIT_VERTICAL else LetterSlot(2, 0, part)
    return None


def code_slot(code):
    """Pełny kod EWM („Z1-07-300P-1”) → LetterSlot albo None (brak litery / nieznana /
    4-członowy kod generatora „Z1-01-100-2X”, gdzie litera jest kolumną, nie poziomem)."""
    parts = (code or "").strip().upper().split("-")
    if len(parts) < 3 or not parts[2][-1:].isalpha():
        return None
    half = parts[3] if len(parts) > 3 and parts[3] in ("1", "2") else 0
    return letter_slot(parts[0], parts[2][-1], int(half))


def letter_rank(letter):
    """Klucz sortowania liter od podłogi w górę: (poziom, półka); nieznane litery na końcu."""
    slot = letter_slot("", letter)
    return (slot.level, slot.shelf, letter) if slot else (99, 0, letter)


# Ile półek/części dzieli otwór poziomu: P/Q/R → 3 w poziomie 1, S/T → 2 w poziomie 2.
_SHELVES_IN_OPENING = {1: 3, 2: 2}


def shelves_in_opening(slot):
    """Na ile części (w pionie) dzielony jest otwór poziomu danej półki; całe miejsce → 1."""
    if not slot or not slot.shelf:
        return 1
    return _SHELVES_IN_OPENING.get(slot.level, slot.shelf)


def letter_level(zone, letter, default=None):
    """Sam numer poziomu 1..8 (``default`` dla nieznanej litery)."""
    slot = letter_slot(zone, letter)
    return slot.level if slot else default


def level_height_keys(zone, letter, level):
    """Klucze ``WarehouseRackType.level_heights`` w kolejności wyszukiwania.

    Półka/część poziomu (P/Q/R w poz. 1, S/T w poz. 2) najpierw szuka własnej wysokości
    „1P”/„1Q”/„1R”/„2S”/„2T”, potem wysokości całego poziomu „1”/„2”. Pełne miejsca → „<poziom>”."""
    slot = letter_slot(zone, letter)
    base, _ = _split_letter(letter, 0)
    keys = [str(level)]
    if slot and slot.shelf:
        keys.insert(0, f"{level}{base}")
    return keys
