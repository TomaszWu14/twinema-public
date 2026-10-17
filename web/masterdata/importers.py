"""Import plików z danymi (xlsx / csv) — czysty Python, bez Django.

`read_table` zamienia plik na nagłówki + wiersze, `map_columns` dopasowuje nagłówki do pól
po aliasach (PL/EN/WMS), a `parse_<rodzaj>` waliduje wiersz: zwraca (dane, None) albo
(None, powód odrzucenia). Widok tylko zapisuje wynik i raport.
"""
import csv
import io
import re
import unicodedata
from datetime import date, datetime

MAX_ROWS = 300_000
MAX_XLSX_BYTES = 400 * 1024 * 1024     # xlsx po rozpakowaniu (plik do 25 MB; przegląd SEC)
REJECT_SAMPLE = 200

# pole → aliasy nagłówków (porównywane po normalizacji: małe litery, bez ogonków i znaków).
ALIASES = {
    "materials": {
        "code": ["kod", "kod materialu", "material", "materiał", "sku", "indeks", "produkt", "matnr", "code"],
        "name": ["nazwa", "opis", "nazwa materialu", "name", "description"],
        "group": ["grupa", "grupa towarowa", "kategoria", "group", "category", "h1"],
        "unit": ["jednostka", "jm", "jednostka bazowa", "unit", "uom"],
        "pcs_per_carton": ["szt w kartonie", "sztuk w kartonie", "szt/karton", "pcs per carton", "pcs_per_carton"],
        "carton_l_cm": ["karton dl", "karton dlugosc", "dlugosc kartonu", "carton length", "carton_l_cm"],
        "carton_w_cm": ["karton szer", "karton szerokosc", "szerokosc kartonu", "carton width", "carton_w_cm"],
        "carton_h_cm": ["karton wys", "karton wysokosc", "wysokosc kartonu", "carton height", "carton_h_cm"],
        "carton_kg": ["karton waga", "waga kartonu", "carton weight", "carton_kg"],
        "cartons_per_pallet": ["kartonow na palecie", "kartony na palecie", "cartons per pallet", "cartons_per_pallet"],
        "pallet_h_cm": ["wys palety", "wysokosc palety", "pallet height", "pallet_h_cm"],
        "piece_l_cm": ["sztuka dl", "sztuka dlugosc", "dlugosc sztuki", "piece length", "piece_l_cm"],
        "piece_w_cm": ["sztuka szer", "sztuka szerokosc", "szerokosc sztuki", "piece width", "piece_w_cm"],
        "piece_h_cm": ["sztuka wys", "sztuka wysokosc", "wysokosc sztuki", "piece height", "piece_h_cm"],
        "piece_kg": ["sztuka waga", "waga sztuki", "piece weight", "piece_kg"],
        "cartons_per_layer": ["kartonow na warstwe", "kartony na warstwe", "cartons per layer", "cartons_per_layer"],
        "layers_per_pallet": ["warstw na palecie", "warstwy na palecie", "layers per pallet", "layers_per_pallet"],
        "carrier": ["nosnik", "typ palety", "carrier", "pallet type"],
        "height_class": ["klasa wysokosci", "height class"],
        "weight_class": ["klasa wagi", "weight class"],
        "abc_manual": ["abc", "klasa abc", "abc class"],
        "temp_controlled": ["temperatura", "temperatura kontrolowana", "chlodnia", "temp controlled"],
        "adr": ["adr", "niebezpieczny", "towar niebezpieczny", "dangerous goods"],
        "oversize": ["gabaryt", "dluzyca", "ponadgabaryt", "oversize"],
        "high_value": ["wysoka wartosc", "wartosciowy", "high value"],
    },
    "locations": {
        "location_code": ["lokalizacja", "kod lokalizacji", "miejsce skladowania", "location", "bin", "code", "kod"],
        "warehouse_type": ["typ", "typ magazynu", "typ miejsca", "typ ewm", "warehouse type", "storage type"],
        "level": ["poziom", "level"],
        "height_mm": ["wysokosc mm", "wysokosc", "max wysokosc", "height mm", "height"],
        "width_mm": ["szerokosc mm", "szerokosc", "width mm", "width"],
        "depth_mm": ["glebokosc mm", "glebokosc", "depth mm", "depth"],
        "max_weight_kg": ["max waga", "nosnosc", "max waga kg", "max weight", "max_weight_kg"],
        "max_volume_m3": ["max objetosc", "objetosc m3", "max volume", "max_volume_m3"],
        "blocked_pick": ["blokada wydania", "blokada pobrania", "blocked pick"],
        "blocked_put": ["blokada umieszczania", "blokada przyjecia", "blocked put"],
    },
    "stock": {
        "location_code": ["lokalizacja", "kod lokalizacji", "miejsce skladowania", "location", "bin"],
        "material_code": ["material", "materiał", "kod materialu", "produkt", "sku", "indeks", "matnr"],
        "qty": ["ilosc", "ilość", "stan", "quantity", "qty"],
        "unit": ["jednostka", "jm", "unit", "uom"],
        "hu": ["hu", "nosnik", "sscc", "jednostka magazynowa", "handling unit"],
        "lot": ["partia", "seria", "lot", "batch"],
        "expiry": ["data waznosci", "waznosc", "termin waznosci", "expiry", "best before"],
    },
}
REQUIRED = {"materials": ["code"], "locations": ["location_code"], "stock": ["location_code", "material_code"]}
LABELS = {
    "code": "kod materiału", "name": "nazwa", "group": "grupa towarowa", "unit": "jednostka",
    "pcs_per_carton": "szt w kartonie", "carton_l_cm": "karton dł [cm]", "carton_w_cm": "karton szer [cm]",
    "carton_h_cm": "karton wys [cm]", "carton_kg": "karton waga [kg]", "cartons_per_pallet": "kartonów na palecie",
    "pallet_h_cm": "wys palety [cm]", "location_code": "lokalizacja", "warehouse_type": "typ",
    "level": "poziom", "height_mm": "wysokość [mm]", "width_mm": "szerokość [mm]", "depth_mm": "głębokość [mm]",
    "max_weight_kg": "max waga [kg]", "max_volume_m3": "max objętość [m3]", "blocked_pick": "blokada wydania",
    "blocked_put": "blokada umieszczania", "material_code": "materiał", "qty": "ilość", "hu": "HU",
    "lot": "partia", "expiry": "data ważności",
    "piece_l_cm": "sztuka dł [cm]", "piece_w_cm": "sztuka szer [cm]", "piece_h_cm": "sztuka wys [cm]",
    "piece_kg": "sztuka waga [kg]", "cartons_per_layer": "kartonów na warstwę", "layers_per_pallet": "warstw na palecie",
    "carrier": "nośnik", "height_class": "klasa wysokości", "weight_class": "klasa wagi", "abc_manual": "klasa ABC",
    "temp_controlled": "temperatura kontrolowana", "adr": "ADR", "oversize": "gabaryt / dłużyca",
    "high_value": "wysoka wartość",
}
MATERIAL_REFS = ("carrier", "height_class", "weight_class")      # nazwy → FK rozwiązuje services
MATERIAL_FLAGS = ("temp_controlled", "adr", "oversize", "high_value")
CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{0,49}$")


class ImportFileError(ValueError):
    """Pliku nie da się odczytać jako tabeli — komunikat dla użytkownika."""


def norm(text):
    """Nagłówek → klucz porównania: małe litery, bez ogonków, tylko litery/cyfry/spacje."""
    # „ł” nie rozkłada się w NFKD (to osobna litera, nie l + znak) — zamiana jawna.
    s = str(text or "").replace("ł", "l").replace("Ł", "L")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9/]+", " ", s).split())


class _SemicolonExcel(csv.excel):
    delimiter = ";"


def read_table(name, data):
    """(nazwa pliku, bajty) → (nagłówki, wiersze jako listy). xlsx/xlsm albo csv/txt (; , TAB)."""
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext in ("xlsx", "xlsm"):
        import openpyxl

        from twin.xlsx import check_xlsx_size
        try:
            check_xlsx_size(io.BytesIO(data), MAX_XLSX_BYTES)
        except ValueError as exc:
            raise ImportFileError(str(exc)) from exc
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:
            raise ImportFileError(f"Nie udało się otworzyć pliku Excel ({exc.__class__.__name__}).") from exc
        it = wb.worksheets[0].iter_rows(values_only=True)
        rows = []
        for row in it:
            if any(v not in (None, "") for v in row):
                rows.append(list(row))
            if len(rows) > MAX_ROWS + 1:
                raise ImportFileError(f"Plik ma więcej niż {MAX_ROWS} wierszy — podziel go.")
        wb.close()
    elif ext in ("csv", "txt"):
        text = data.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
        except csv.Error:
            dialect = _SemicolonExcel          # nie zmieniamy csv.excel — to wspólny obiekt całego procesu
        rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
        if len(rows) > MAX_ROWS + 1:
            raise ImportFileError(f"Plik ma więcej niż {MAX_ROWS} wierszy — podziel go.")
    else:
        raise ImportFileError("Obsługiwane pliki: .xlsx, .csv.")
    if not rows:
        raise ImportFileError("Plik jest pusty.")
    return [str(h or "").strip() for h in rows[0]], rows[1:]


def map_columns(kind, headers):
    """{pole: indeks kolumny} — pierwsze trafienie aliasu (dokładne przed „zawiera”)."""
    keys = [norm(h) for h in headers]
    out = {}
    for field, aliases in ALIASES[kind].items():
        wanted = [norm(a) for a in aliases]
        idx = next((i for i, k in enumerate(keys) if k in wanted and i not in out.values()), None)
        if idx is None:
            idx = next((i for i, k in enumerate(keys) for a in wanted
                        if len(a) > 3 and a in k and i not in out.values()), None)
        if idx is not None:
            out[field] = idx
    return out


def missing_required(kind, cols):
    return [LABELS[f] for f in REQUIRED[kind] if f not in cols]


def _cell(row, cols, field):
    i = cols.get(field)
    if i is None or i >= len(row):
        return None
    v = row[i]
    return v.strip() if isinstance(v, str) else v


def _text(v, upper=False):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s.upper() if upper else s


def _num(v, field, *, positive=True, integer=False):
    """'40,5' → 40.5; puste → None; zła wartość → ValueError z nazwą pola."""
    if v in (None, ""):
        return None
    try:
        x = float(str(v).replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        raise ValueError(f"{LABELS[field]}: „{v}” to nie liczba") from None
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError(f"{LABELS[field]}: „{v}” to nie liczba")
    if positive and x < 0:
        raise ValueError(f"{LABELS[field]}: wartość ujemna")
    return round(x) if integer else x


def _bool(v):
    return norm(v) in ("1", "x", "tak", "t", "y", "yes", "true", "prawda")


def _date(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data ważności: „{s}” — użyj RRRR-MM-DD albo DD.MM.RRRR")


def _code(v, field):
    s = _text(v, upper=True)
    if not s:
        raise ValueError(f"brak: {LABELS[field]}")
    if not CODE_RE.match(s):
        raise ValueError(f"{LABELS[field]}: niedozwolone znaki w „{s[:60]}”")
    return s


MATERIAL_INTS = ("pcs_per_carton", "cartons_per_pallet", "cartons_per_layer", "layers_per_pallet")
MATERIAL_FLOATS = ("carton_l_cm", "carton_w_cm", "carton_h_cm", "carton_kg", "pallet_h_cm",
                   "piece_l_cm", "piece_w_cm", "piece_h_cm", "piece_kg")


def parse_material(row, cols):
    """Wiersz → dict pól materiału. Nośnik i klasy jako nazwy (FK rozwiązuje services);
    flagi stref specjalnych jako bool (TAK/X/1)."""
    try:
        abc = _text(_cell(row, cols, "abc_manual"), upper=True)
        if abc not in ("", "A", "B", "C"):
            raise ValueError(f"klasa ABC: „{abc[:10]}” — dozwolone A, B, C albo puste")
        out = {
            "code": _code(_cell(row, cols, "code"), "code"),
            "name": _text(_cell(row, cols, "name"))[:200],
            "group": _text(_cell(row, cols, "group"))[:80],
            "unit": (_text(_cell(row, cols, "unit"), upper=True) or "SZT")[:10],
            "abc_manual": abc,
        }
        for f in MATERIAL_INTS:
            out[f] = _num(_cell(row, cols, f), f, integer=True)
        for f in MATERIAL_FLOATS:
            out[f] = _num(_cell(row, cols, f), f)
        for f in MATERIAL_REFS:
            out[f] = _text(_cell(row, cols, f))[:60]
        for f in MATERIAL_FLAGS:
            out[f] = _bool(_cell(row, cols, f))
        return out, None
    except ValueError as exc:
        return None, str(exc)


def parse_location(row, cols, level_of=None):
    """`level_of(kod)` — poziom z litery kodu, gdy plik nie ma kolumny poziomu."""
    try:
        code = _code(_cell(row, cols, "location_code"), "location_code")
        level = _num(_cell(row, cols, "level"), "level", integer=True)
        return {
            "location_code": code,
            "warehouse_type": _text(_cell(row, cols, "warehouse_type"), upper=True)[:50],
            "level": level or (level_of(code) if level_of else None) or 1,
            "height_mm": _num(_cell(row, cols, "height_mm"), "height_mm", integer=True) or 0,
            "width_mm": _num(_cell(row, cols, "width_mm"), "width_mm", integer=True) or 0,
            "depth_mm": _num(_cell(row, cols, "depth_mm"), "depth_mm", integer=True) or 0,
            "max_weight_kg": _num(_cell(row, cols, "max_weight_kg"), "max_weight_kg") or 0.0,
            "max_volume_m3": _num(_cell(row, cols, "max_volume_m3"), "max_volume_m3") or 0.0,
            "blocked_pick": _bool(_cell(row, cols, "blocked_pick")),
            "blocked_put": _bool(_cell(row, cols, "blocked_put")),
        }, None
    except ValueError as exc:
        return None, str(exc)


def parse_stock(row, cols):
    try:
        qty = _num(_cell(row, cols, "qty"), "qty")
        return {
            "location_code": _code(_cell(row, cols, "location_code"), "location_code"),
            "material_code": _code(_cell(row, cols, "material_code"), "material_code"),
            "qty": qty if qty is not None else 0.0,
            "unit": _text(_cell(row, cols, "unit"), upper=True)[:10],
            "hu": _text(_cell(row, cols, "hu"))[:40],
            "lot": _text(_cell(row, cols, "lot"))[:40],
            "expiry": _date(_cell(row, cols, "expiry")),
        }, None
    except ValueError as exc:
        return None, str(exc)


PARSERS = {"materials": parse_material, "locations": parse_location, "stock": parse_stock}


def parse_rows(kind, rows, cols, **kw):
    """→ (poprawne dicty, odrzucone [{row, reason}] — próbka), liczba odrzuconych.
    Duplikat klucza (materiał, lokalizacja) → ostatni wiersz wygrywa w zapisie, tu bez odrzucania."""
    ok, rejects, n_rej = [], [], 0
    parse = PARSERS[kind]
    for n, row in enumerate(rows, start=2):        # 1 = nagłówek
        data, err = parse(row, cols, **kw)
        if err:
            n_rej += 1
            if len(rejects) < REJECT_SAMPLE:
                rejects.append({"row": n, "reason": err})
        else:
            ok.append(data)
    return ok, rejects, n_rej


def template_csv(kind):
    """Wzór pliku: nagłówki (pierwszy alias = polska nazwa) — do pobrania z ekranu Dane."""
    return ";".join(LABELS[f] for f in ALIASES[kind]) + "\n"
