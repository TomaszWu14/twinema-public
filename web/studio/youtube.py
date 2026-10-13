"""Opis filmu na YouTube: rozdziały z osi czasu montażu (plansza tytułowa → ujęcia → plansza końcowa).

Zasady YouTube dla rozdziałów: pierwszy od 00:00, co najmniej 3, każdy ≥ 10 s — krótsze ujęcia doklejane są
do poprzedniego rozdziału; za mało rozdziałów → lista pusta (YouTube i tak by ich nie pokazał).
"""
import re

MIN_CHAPTER_S = 10.0
MIN_CHAPTERS = 3
LABEL_CHARS = 60


def label(text):
    """Etykieta rozdziału: pierwsze zdanie kwestii, przycięte na granicy słowa."""
    first = re.split(r"(?<=[.!?…])\s", " ".join(text.split()), maxsplit=1)[0].rstrip(".")
    if len(first) <= LABEL_CHARS:
        return first
    return first[:LABEL_CHARS].rsplit(" ", 1)[0].rstrip(",;:—-– ") + "…"


def stamp(t):
    t = int(t)
    h, m, s = t // 3600, t // 60 % 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def chapters(title_s, shots, end_s):
    """shots: [(długość_s, tekst kwestii)] → [(start_s, etykieta)]. Plansza tytułowa należy do 1. rozdziału,
    końcowa do ostatniego."""
    out = []                                   # [start, etykieta, długość]
    t = title_s
    for i, (dur, text) in enumerate(shots):
        if i == 0:
            out.append([0.0, label(text), title_s + dur])
        elif out[-1][2] < MIN_CHAPTER_S:
            out[-1][2] += dur                  # poprzedni rozdział za krótki — ujęcie dokleja się do niego
        else:
            out.append([t, label(text), dur])
        t += dur
    if out:
        out[-1][2] += end_s
        if len(out) > 1 and out[-1][2] < MIN_CHAPTER_S:
            out[-2][2] += out.pop()[2]
    return [(start, lab) for start, lab, _ in out] if len(out) >= MIN_CHAPTERS else []


def description(title, chapter_list, *, demo_url="", app_name="TWINEMA"):
    """Gotowy opis do wklejenia w YouTube Studio."""
    lines = [title, "",
             f"{app_name} — cyfrowy bliźniak magazynu: hala w 3D, symulacja dnia pracy i prezentacja dla zarządu.",
             "Dane w filmie są syntetyczne."]
    if demo_url:
        lines += ["", f"Wersja demo bez logowania: {demo_url}"]
    if chapter_list:
        lines += ["", "Rozdziały:"] + [f"{stamp(t)} {lab}" for t, lab in chapter_list]
    return "\n".join(lines) + "\n"
