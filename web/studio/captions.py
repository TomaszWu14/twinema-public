"""Napisy filmu (czysty Python — bez Django i bez sieci). Film nie ma lektora: tekst ujęcia jest
wypalony w obrazie, a długość ujęcia wynika z czasu potrzebnego na jego przeczytanie.

  • `shot_seconds` — długość ujęcia z liczby słów (tempo czytania + zapas), 5–60 s.
  • `timed_words` / `shot_cues` — słowa rozłożone po czasie ujęcia → plansze napisów.
  • `cues` — podział tekstu na plansze: ≤ 2 linie po ≤ 42 znaki, ≤ 6 s na planszę.
  • `build_srt` — plik SRT z ujęć przesuniętych o ich początek na osi filmu.
"""
LINE_CHARS, MAX_LINES, MAX_CUE_S = 42, 2, 6.0
READ_WPS = 2.2                  # słów/s — napis czytany obok oglądanej sceny (wolniej niż sam tekst)
PAD_S = 1.5                     # wejście + zejście napisu
LEAD_S, TAIL_S = 0.4, 0.6       # pierwszy napis po wejściu ujęcia, ostatni znika przed cięciem
MIN_SHOT_S, MAX_SHOT_S = 5.0, 60.0


def shot_seconds(text):
    """Czas ujęcia: tyle, ile trzeba na przeczytanie napisu (spokojne tempo, bo widz patrzy też na scenę)
    + zapas na wejście i zejście napisu; w granicach kolejki renderów."""
    n = len(text.split())
    return min(MAX_SHOT_S, max(MIN_SHOT_S, round(n / READ_WPS + PAD_S, 1)))


def timed_words(text, seconds):
    """[(słowo, start, koniec)] — słowa rozłożone po czasie ujęcia proporcjonalnie do długości
    (od LEAD_S do seconds − TAIL_S); zastępuje znaczniki czasu z nagrania lektora."""
    ws = text.split()
    if not ws:
        return []
    t0, t1 = LEAD_S, max(seconds - TAIL_S, LEAD_S + 0.1)
    per = (t1 - t0) / sum(len(w) + 1 for w in ws)
    out, t = [], t0
    for w in ws:
        d = (len(w) + 1) * per
        out.append((w, round(t, 3), round(t + d, 3)))
        t += d
    return out


def shot_cues(text, seconds):
    """Napisy jednego ujęcia: [(start, koniec, tekst z \\n)] na osi ujęcia."""
    return cues(timed_words(text, seconds))


def _wrap(ws):
    """Słowa → linie po ≤ LINE_CHARS znaków."""
    lines = [""]
    for w in ws:
        if lines[-1] and len(lines[-1]) + 1 + len(w) > LINE_CHARS:
            lines.append(w)
        else:
            lines[-1] = f"{lines[-1]} {w}".strip()
    return lines


def cues(word_times):
    """Słowa z czasami → [(start, koniec, tekst z \\n)]. Nowa plansza, gdy przekroczony limit
    linii albo czasu; po kropce plansza się kończy, jeśli ma już ≥ 1 linię treści."""
    out, cur = [], []
    for w in word_times:
        trial = cur + [w]
        too_long = len(_wrap([x[0] for x in trial])) > MAX_LINES or (cur and w[2] - cur[0][1] > MAX_CUE_S)
        if cur and too_long:
            out.append(cur)
            cur = [w]
        else:
            cur = trial
        if cur and cur[-1][0].endswith((".", "!", "?")) and len(" ".join(x[0] for x in cur)) >= LINE_CHARS * 0.6:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [(c[0][1], c[-1][2], "\n".join(_wrap([x[0] for x in c]))) for c in out]


def srt_time(t):
    ms = int(round(max(t, 0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments):
    """segments: [(przesunięcie_s, cues)] → tekst SRT (numeracja od 1, CRLF niepotrzebny)."""
    blocks = []
    for offset, cs in segments:
        for start, end, text in cs:
            blocks.append(f"{len(blocks) + 1}\n{srt_time(offset + start)} --> {srt_time(offset + end)}\n{text}\n")
    return "\n".join(blocks)


def offsets(durations, gap_s=0.0, start_s=0.0):
    """Początki kolejnych ujęć na osi filmu (gap = pauza między ujęciami)."""
    out, t = [], start_s
    for d in durations:
        out.append(round(t, 3))
        t += d + gap_s
    return out
