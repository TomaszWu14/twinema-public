"""Eksport XLSX z neutralizacją formuł (CSV/formula injection)."""
import io

from django.http import HttpResponse

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(v):
    """Tekst zaczynający się od = + - @ TAB CR → prefiks `'`. Liczby bez zmian."""
    if isinstance(v, str) and v.startswith(_FORMULA_PREFIXES):
        return "'" + v
    return v


MAX_XLSX_RATIO = 200      # zwykły xlsx kompresuje się 5–50×; więcej = podejrzenie „bomby” ZIP


def check_xlsx_size(src, max_bytes):
    """Przegląd SEC (7): xlsx to ZIP — przed otwarciem w openpyxl (wczytuje sharedStrings w całości do pamięci)
    sprawdza rozmiar po rozpakowaniu i współczynnik kompresji. `src` = ścieżka albo plik binarny; ValueError z opisem."""
    import zipfile
    try:
        with zipfile.ZipFile(src) as z:
            infos = z.infolist()
    except zipfile.BadZipFile:
        return                                   # uszkodzony plik zgłosi openpyxl swoim komunikatem
    total = sum(i.file_size for i in infos)
    packed = sum(i.compress_size for i in infos) or 1
    if total > max_bytes or total / packed > MAX_XLSX_RATIO:
        raise ValueError(f"Plik Excel po rozpakowaniu ma {total // (1024 * 1024)} MB — za dużo albo podejrzanie "
                         "wysoka kompresja. Zapisz dane jako CSV albo podziel plik.")


def _make_xlsx_response(filename: str):
    """(workbook, worksheet, HttpResponse) gotowe do wypełnienia."""
    import openpyxl
    wb = openpyxl.Workbook()
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return wb, wb.active, response


def _finalize_xlsx(wb, ws, response):
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for c in row:
                if c.data_type == "f" and isinstance(c.value, str):
                    c.value = safe_cell(c.value)
    buf = io.BytesIO()
    wb.save(buf)
    response.content = buf.getvalue()
    return response
