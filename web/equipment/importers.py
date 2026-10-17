"""Import własnych modeli sprzętu z xlsx/csv (K2) — czysty Python poza zapisem w `import_rows`.

Wiersz → dict pól `Equipment`; braki prędkości/parametrów uzupełnia klasa ogólna tego typu (uwagi mówią
skąd). Klasy systemowe są nietykalne; istniejący własny model o tej samej nazwie jest aktualizowany.
"""
import io

from masterdata.importers import ImportFileError, norm, read_table

from .catalog import ATTACHMENTS, KINDS

# pole → (nagłówek wzoru, aliasy)
COLUMNS = {
    "kind": ("Typ", ["typ", "rodzaj", "kategoria"]),
    "name": ("Nazwa", ["nazwa", "model"]),
    "manufacturer": ("Producent", ["producent", "marka"]),
    "capacity_kg": ("Udźwig [kg]", ["udzwig", "udzwig kg", "maks udzwig"]),
    "max_lift_m": ("Maks. podnoszenie [m]", ["maks podnoszenie", "wysokosc podnoszenia", "maks wys podn"]),
    "lift_curve": ("Krzywa udźwigu (wys:kg;…)", ["krzywa udzwigu", "redukcja udzwigu"]),
    "speed_loaded_kmh": ("Jazda z ładunkiem [km/h]", ["jazda z ladunkiem", "predkosc z ladunkiem"]),
    "speed_empty_kmh": ("Jazda bez ładunku [km/h]", ["jazda bez ladunku", "predkosc bez ladunku"]),
    "lift_speed_ms": ("Podnoszenie [m/s]", ["podnoszenie m/s", "predkosc podnoszenia"]),
    "lower_speed_ms": ("Opuszczanie [m/s]", ["opuszczanie", "predkosc opuszczania"]),
    "aisle_m": ("Alejka Ast [m]", ["alejka", "ast"]),
    "battery_h": ("Bateria [h]", ["bateria", "praca na baterii"]),
    "charge_h": ("Ładowanie [h]", ["ladowanie"]),
    "attachments": ("Osprzęt", ["osprzet"]),
    "cost_purchase": ("Zakup od [zł]", ["zakup od", "cena od"]),
    "cost_purchase_max": ("Zakup do [zł]", ["zakup do", "cena do"]),
    "notes": ("Uwagi", ["uwagi"]),
}
NUMBERS = ["capacity_kg", "max_lift_m", "speed_loaded_kmh", "speed_empty_kmh", "lift_speed_ms", "lower_speed_ms",
           "aisle_m", "battery_h", "charge_h", "cost_purchase", "cost_purchase_max"]
FILLED_FROM_CLASS = ["speed_loaded_kmh", "speed_empty_kmh", "lift_speed_ms", "lower_speed_ms", "aisle_m", "pick_s",
                     "drop_s", "battery_h", "charge_h", "turn_radius_m", "length_m", "width_m"]
KIND_BY_LABEL = {norm(label): code for code, label in KINDS} | {norm(code): code for code, _ in KINDS}
ATT_BY_LABEL = {norm(v[0]): k for k, v in ATTACHMENTS.items()} | {norm(k): k for k in ATTACHMENTS}


def template_xlsx():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sprzęt"
    ws.append([h for h, _ in COLUMNS.values()])
    ws.append(["Reach truck (wysokiego składowania)", "Model testowy A", "", 1600, 10, "6:1600;10:1000", 11, 12,
               0.4, 0.5, 2.9, 6, 2, "Przesuw boczny", 180000, 250000, ""])
    lists = wb.create_sheet("Słowniki")
    lists.append(["Typy", "Osprzęt (rozdziel ; )"])
    for i in range(max(len(KINDS), len(ATTACHMENTS))):
        lists.append([KINDS[i][1] if i < len(KINDS) else None,
                      list(ATTACHMENTS.values())[i][0] if i < len(ATTACHMENTS) else None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _cols(headers):
    keys = [norm(h) for h in headers]
    out = {}
    for field, (label, aliases) in COLUMNS.items():
        wanted = [norm(label), *[norm(a) for a in aliases]]
        idx = next((i for i, k in enumerate(keys) if k in wanted and i not in out.values()), None)
        if idx is None:
            idx = next((i for i, k in enumerate(keys) for a in wanted if len(a) > 3 and a in k
                        and i not in out.values()), None)
        if idx is not None:
            out[field] = idx
    return out


def _num(v, label):
    if v in (None, ""):
        return None
    try:
        x = float(str(v).replace(" ", "").replace("\xa0", "").replace(",", "."))
    except ValueError:
        raise ValueError(f"{label}: „{v}” to nie liczba") from None
    if x != x or x < 0:
        raise ValueError(f"{label}: wartość ujemna albo niepoprawna")
    return x


def _curve(v):
    if v in (None, ""):
        return []
    pts = []
    for part in str(v).replace(",", ".").split(";"):
        if part.strip():
            h, _, kg = part.partition(":")
            pts.append([float(h), round(float(kg))])
    return sorted(pts)


def parse_row(row, cols):
    """Wiersz → dict pól; ValueError z opisem dla raportu odrzuceń."""
    def cell(f):
        i = cols.get(f)
        v = row[i] if i is not None and i < len(row) else None
        return v.strip() if isinstance(v, str) else v
    name = str(cell("name") or "").strip()[:120]
    if not name:
        raise ValueError("brak nazwy")
    kind = KIND_BY_LABEL.get(norm(cell("kind")))
    if not kind:
        raise ValueError(f"nieznany typ „{cell('kind')}”")
    out = {"name": name, "kind": kind, "manufacturer": str(cell("manufacturer") or "").strip()[:80],
           "notes": str(cell("notes") or "").strip()}
    for f in NUMBERS:
        out[f] = _num(cell(f), COLUMNS[f][0])
    if not out["capacity_kg"]:
        raise ValueError("brak udźwigu")
    out["capacity_kg"] = round(out["capacity_kg"])
    try:
        out["lift_curve"] = _curve(cell("lift_curve"))
    except ValueError:
        raise ValueError("krzywa udźwigu: format „wys:kg;wys:kg”") from None
    att = []
    for part in str(cell("attachments") or "").split(";"):
        if part.strip():
            code = ATT_BY_LABEL.get(norm(part))
            if not code:
                raise ValueError(f"nieznany osprzęt „{part.strip()}”")
            att.append(code)
    out["attachments"] = att
    return out


def parse_file(name, data):
    """→ (wiersze poprawne, odrzucone [(nr wiersza, powód)])."""
    headers, rows = read_table(name, data)
    cols = _cols(headers)
    if "name" not in cols or "kind" not in cols:
        raise ImportFileError("Brak kolumn „Typ” i „Nazwa” — pobierz wzór pliku.")
    ok, bad = [], []
    for n, row in enumerate(rows, start=2):
        try:
            ok.append(parse_row(row, cols))
        except ValueError as exc:
            bad.append((n, str(exc)))
    return ok, bad


def import_rows(rows, user):
    """Zapis: własny model po nazwie (tworzy albo aktualizuje), braki z klasy ogólnej typu.
    Klas systemowych nie rusza; cudzego modelu (inny autor albo brak autora) nie aktualizuje — chyba że
    importuje administrator. → (utworzone, zaktualizowane, pominięte [(nazwa, powód)])."""
    from core.roles import GROUP_ADMIN, has_role

    from .models import Equipment
    created = updated = 0
    skipped = []
    admin = has_role(user, GROUP_ADMIN)
    for r in rows:
        if Equipment.objects.filter(name=r["name"], is_system=True).exists():
            skipped.append((r["name"], "nazwa klasy systemowej — zmień nazwę"))
            continue
        if not admin and Equipment.objects.filter(name=r["name"], is_system=False).exclude(created_by=user).exists():
            skipped.append((r["name"], "model innego użytkownika — zmień nazwę"))
            continue
        base = Equipment.objects.filter(is_system=True, kind=r["kind"]).order_by("capacity_kg").first()
        filled = [f for f in FILLED_FROM_CLASS if r.get(f) is None and base and getattr(base, f) is not None]
        vals = {k: v for k, v in r.items() if v is not None}
        for f in filled:
            vals[f] = getattr(base, f)
        for f in ("speed_loaded_kmh", "speed_empty_kmh"):
            vals.setdefault(f, 5.0)
        if filled:
            note = f"Z klasy ogólnej „{base.name}”: " + ", ".join(Equipment._meta.get_field(f).verbose_name
                                                               for f in filled)
            vals["notes"] = (vals.get("notes", "") + "\n" + note).strip()
        _, new = Equipment.objects.update_or_create(name=r["name"], is_system=False, defaults=vals,
                                                    create_defaults=vals | {"created_by": user})
        created, updated = created + new, updated + (not new)
    return created, updated, skipped
