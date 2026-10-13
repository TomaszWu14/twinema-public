"""Deck PDF prezentacji (czysty Python — fpdf2, bez Django i bez bazy).

Strony 16:9: tytułowa → liczby z KPI (kafle) → ujęcie na stronę (kadr + tekst ujęcia) → końcowa.
Font DejaVu Sans (w repo, studio/fonts) — polskie znaki bez zależności od systemu.
"""
import io
import logging
from pathlib import Path

from fpdf import FPDF

logging.getLogger("fontTools").setLevel(logging.WARNING)      # subsetting fontu loguje każdy glif na INFO
FONTS = Path(__file__).resolve().parent / "fonts"
W, H = 338.67, 190.5                              # 13,33 × 7,5 cala — jak slajd 16:9
M = 16                                            # margines
BG, SURFACE, FG, MUTED, ACCENT = (15, 17, 21), (26, 29, 36), (236, 238, 242), (150, 156, 168), (240, 162, 58)


def split_fact(fact):
    """„Etykieta: wartość.” → (etykieta, wartość) do kafla; zdanie bez dwukropka → ("", zdanie)."""
    label, sep, value = fact.partition(": ")
    return (label, value.rstrip(".")) if sep else ("", fact.rstrip("."))


class _Deck(FPDF):
    def __init__(self, app_name):
        super().__init__(orientation="L", unit="mm", format=(H, W))
        self.app_name = app_name
        self.set_auto_page_break(False)
        self.c_margin = 0                         # akapity równo z nagłówkami (bez wcięcia komórki)
        self.add_font("DejaVu", "", str(FONTS / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS / "DejaVuSans-Bold.ttf"))
        self.set_title(app_name)

    def new_slide(self):
        self.add_page()
        self.set_fill_color(*BG)
        self.rect(0, 0, W, H, style="F")
        if self.page_no() > 1:                    # stopka: marka + numer strony
            self.text_at(M, H - 8, self.app_name.upper(), 8, ACCENT, bold=True)
            self.set_xy(W - M - 30, H - 11)
            self.set_font("DejaVu", "", 8)
            self.set_text_color(*MUTED)
            self.cell(30, 5, str(self.page_no()), align="R")

    def text_at(self, x, y, text, size, color, bold=False):
        self.set_font("DejaVu", "B" if bold else "", size)
        self.set_text_color(*color)
        self.text(x, y, text)

    def para(self, x, y, w, text, size, color, bold=False, line=1.45, align="L"):
        self.set_xy(x, y)
        self.set_font("DejaVu", "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(w, size * 0.3528 * line, text, align=align)


def build_deck(title, app_name, date_str, facts, slides):
    """slides: [{"label": "Przelot nad halą", "text": kwestia, "image": bytes PNG albo None}] → bytes PDF."""
    pdf = _Deck(app_name)

    pdf.new_slide()                               # tytułowa
    pdf.text_at(M + 4, 52, app_name.upper(), 12, ACCENT, bold=True)
    pdf.para(M + 4, 64, W - 2 * M - 40, title, 34, FG, bold=True, line=1.25)
    pdf.text_at(M + 4, H - 30, f"Prezentacja projektu magazynu · {date_str}", 12, MUTED)
    pdf.set_fill_color(*ACCENT)
    pdf.rect(M + 4, 40, 28, 1.6, style="F")

    if facts:                                     # liczby — kafle 3 × n
        pdf.new_slide()
        pdf.text_at(M, M + 12, "Projekt w liczbach", 22, FG, bold=True)
        cols, gap, top = 3, 6, M + 24
        tile_w = (W - 2 * M - (cols - 1) * gap) / cols
        rows = -(-len(facts) // cols)
        tile_h = min(44, (H - top - 22 - (rows - 1) * gap) / rows)
        for i, fact in enumerate(facts):
            x, y = M + (i % cols) * (tile_w + gap), top + (i // cols) * (tile_h + gap)
            pdf.set_fill_color(*SURFACE)
            pdf.rect(x, y, tile_w, tile_h, style="F", round_corners=True, corner_radius=2.5)
            label, value = split_fact(fact)
            pdf.para(x + 6, y + 5, tile_w - 12, label or "Wniosek", 9, MUTED)
            pdf.para(x + 6, y + 14, tile_w - 12, value, 15 if label else 12, FG, bold=bool(label), line=1.3)

    for n, s in enumerate(slides, start=1):       # ujęcie na stronę
        pdf.new_slide()
        img_w = 214
        img_h = img_w * 9 / 16
        if s.get("image"):
            pdf.image(io.BytesIO(s["image"]), x=M, y=M, w=img_w, h=img_h)
        else:
            pdf.set_fill_color(*SURFACE)
            pdf.rect(M, M, img_w, img_h, style="F")
            pdf.para(M, M + img_h / 2 - 3, img_w, "Kadr w przygotowaniu", 12, MUTED, align="C")
        tx = M + img_w + 10
        pdf.text_at(tx, M + 6, f"UJĘCIE {n}", 9, ACCENT, bold=True)
        pdf.para(tx, M + 10, W - tx - M, s.get("label", ""), 11, MUTED)
        pdf.para(tx, M + 22, W - tx - M, s.get("text", ""), 13, FG)

    pdf.new_slide()                               # końcowa
    pdf.para(M, H / 2 - 14, W - 2 * M, "Dziękujemy", 34, FG, bold=True)
    pdf.para(M, H / 2 + 4, W - 2 * M, f"{title} · {app_name}", 12, MUTED)
    return bytes(pdf.output())
