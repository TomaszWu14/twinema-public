"""Parser plików modułu Dane — czysty Python (bez bazy)."""
import io
from datetime import date, datetime

import openpyxl
from django.test import SimpleTestCase

from masterdata import importers as im


def _xlsx(rows):
    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class ReadTableTests(SimpleTestCase):
    def test_csv_semicolon_and_comma_and_bom(self):
        for text in ("﻿Kod;Nazwa\nA1;Śruba\n", "Kod,Nazwa\nA1,Śruba\n"):
            headers, rows = im.read_table("m.csv", text.encode("utf-8"))
            self.assertEqual(headers, ["Kod", "Nazwa"])
            self.assertEqual(rows, [["A1", "Śruba"]])

    def test_xlsx_skips_blank_rows(self):
        headers, rows = im.read_table("m.xlsx", _xlsx([["Kod", "Ilość"], ["A1", 5], [None, None], ["A2", 7]]))
        self.assertEqual(headers, ["Kod", "Ilość"])
        self.assertEqual(rows, [["A1", 5], ["A2", 7]])

    def test_xlsx_bomb_rejected_before_opening(self):
        """Przegląd SEC (7): plik o podejrzanie wysokiej kompresji odrzucony przed openpyxl."""
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("xl/sharedStrings.xml", "0" * (20 * 1024 * 1024))
        with self.assertRaisesRegex(im.ImportFileError, "po rozpakowaniu"):
            im.read_table("m.xlsx", buf.getvalue())

    def test_csv_fallback_does_not_change_global_dialect(self):
        """Przegląd SEC (8): plik bez rozpoznanego separatora nie zmienia csv.excel dla reszty procesu."""
        import csv
        im.read_table("m.csv", "Kod\nA1\n".encode())
        self.assertEqual(csv.excel.delimiter, ",")

    def test_bad_files(self):
        with self.assertRaises(im.ImportFileError):
            im.read_table("m.pdf", b"x")
        with self.assertRaises(im.ImportFileError):
            im.read_table("m.xlsx", b"to nie jest excel")
        with self.assertRaises(im.ImportFileError):
            im.read_table("m.csv", b"")


class MapColumnsTests(SimpleTestCase):
    def test_template_headers_map_back_to_every_field(self):
        """Wzór pliku z ekranu Dane musi się importować bez ręcznych poprawek."""
        for kind, aliases in im.ALIASES.items():
            headers = im.template_csv(kind).strip().split(";")
            self.assertEqual(set(im.map_columns(kind, headers)), set(aliases), kind)

    def test_polish_and_wms_headers_any_order(self):
        cols = im.map_columns("stock", ["Ilość", "Partia", "Miejsce składowania", "Produkt", "Data ważności"])
        self.assertEqual(cols, {"qty": 0, "lot": 1, "location_code": 2, "material_code": 3, "expiry": 4})
        self.assertEqual(im.missing_required("stock", {"qty": 0}), ["lokalizacja", "materiał"])

    def test_one_column_feeds_one_field(self):
        cols = im.map_columns("materials", ["Kod", "Kod materiału"])
        self.assertEqual(len(set(cols.values())), len(cols))


class ParseTests(SimpleTestCase):
    def test_material_numbers_with_comma_and_defaults(self):
        cols = im.map_columns("materials", ["kod", "karton waga [kg]", "szt w kartonie"])
        data, err = im.parse_material(["a-1", "4,5", 12.0], cols)
        self.assertIsNone(err)
        self.assertEqual((data["code"], data["carton_kg"], data["pcs_per_carton"], data["unit"]), ("A-1", 4.5, 12, "SZT"))

    def test_material_rejects_with_reason(self):
        cols = im.map_columns("materials", ["kod", "karton waga [kg]"])
        self.assertIn("brak: kod materiału", im.parse_material(["", "1"], cols)[1])
        self.assertIn("to nie liczba", im.parse_material(["A1", "dużo"], cols)[1])
        self.assertIn("ujemna", im.parse_material(["A1", "-2"], cols)[1])
        self.assertIn("niedozwolone znaki", im.parse_material(["A 1", "1"], cols)[1])

    def test_numeric_codes_from_excel_lose_float_suffix(self):
        cols = im.map_columns("stock", ["lokalizacja", "materiał", "ilość"])
        data, _ = im.parse_stock(["V-001-100A", 1000123.0, 3], cols)
        self.assertEqual(data["material_code"], "1000123")

    def test_stock_dates(self):
        cols = im.map_columns("stock", ["lokalizacja", "materiał", "data ważności"])
        for raw in ("2027-01-31", "31.01.2027", datetime(2027, 1, 31), date(2027, 1, 31)):
            self.assertEqual(im.parse_stock(["L1", "M1", raw], cols)[0]["expiry"], date(2027, 1, 31))
        self.assertIn("data ważności", im.parse_stock(["L1", "M1", "jutro"], cols)[1])

    def test_location_level_from_column_or_code(self):
        cols = im.map_columns("locations", ["lokalizacja", "typ"])
        data, _ = im.parse_location(["B0-01-100C", "0010"], cols, level_of=lambda c: 3)
        self.assertEqual((data["level"], data["warehouse_type"], data["blocked_pick"]), (3, "0010", False))
        cols = im.map_columns("locations", ["lokalizacja", "poziom", "blokada wydania"])
        data, _ = im.parse_location(["B0-01-100C", "2", "X"], cols, level_of=lambda c: 3)
        self.assertEqual((data["level"], data["blocked_pick"]), (2, True))

    def test_parse_rows_counts_and_caps_sample(self):
        cols = {"code": 0}
        rows = [[""]] * (im.REJECT_SAMPLE + 5) + [["OK1"]]
        ok, rejects, n = im.parse_rows("materials", rows, cols)
        self.assertEqual((len(ok), n, len(rejects)), (1, im.REJECT_SAMPLE + 5, im.REJECT_SAMPLE))
        self.assertEqual(rejects[0]["row"], 2)                 # numer wiersza w pliku (1 = nagłówek)
