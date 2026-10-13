"""Montaż filmu TWINEMA (tylko biblioteka standardowa — importuje go worker na PC i testy aplikacji).

Oś czasu: plansza tytułowa → ujęcia (długość = nagranie lektora) → plansza końcowa.
Każdy odcinek kodowany identycznie (H.264 yuv420p, AAC 44,1 kHz stereo, stałe fps), potem
`concat` bez ponownego kodowania + napisy SRT jako miękka ścieżka mov_text, +faststart.
Głos każdej kwestii normalizowany do LOUDNESS (YouTube ≈ −14 LUFS) — równy poziom między ujęciami.
Opcjonalny podkład muzyczny (TWINEMA_MUSIC / --music): zapętlony pod całym filmem, cicho, z wygaszeniem na końcu;
wtedy concat koduje ponownie tylko dźwięk.
Komendy to listy argv (bez powłoki) — `run` w workerze wywołuje je po kolei.
"""
import os
import shutil

FPS = 25
CARD_BG = "0x0f1115"          # tło planszy ≈ --bg aplikacji
ACCENT = "0xf0a63a"           # akcent marki
VCODEC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
ACODEC = ["-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]
LOUDNESS = "loudnorm=I=-14:TP=-1.5:LRA=11"
MUSIC_GAIN = 0.12             # podkład ≈ −18 dB pod lektorem
MUSIC_FADE_S = 2.5
FONT_CANDIDATES = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf"]


def find_font(explicit=""):
    """Font z polskimi znakami: TWINEMA_FONT / --font → typowe systemowe."""
    for cand in [explicit, os.environ.get("TWINEMA_FONT", "")] + FONT_CANDIDATES:
        if cand and os.path.isfile(cand):
            return cand
    return ""


def find_music(explicit=""):
    """Podkład muzyczny: --music / TWINEMA_MUSIC → plik albo "" (film bez muzyki)."""
    for cand in (explicit, os.environ.get("TWINEMA_MUSIC", "")):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def find_ffmpeg(explicit=""):
    """FFMPEG_BIN / --ffmpeg → PATH → katalog skrótów winget. Brak → ""."""
    for cand in (explicit, os.environ.get("FFMPEG_BIN", ""), shutil.which("ffmpeg") or ""):
        if cand and os.path.isfile(cand):
            return cand
    winget = os.path.expandvars("%LOCALAPPDATA%/Microsoft/WinGet/Links/ffmpeg.exe")
    return winget if os.path.isfile(winget) else ""


def timeline(title_s, durations, end_s):
    """[(rodzaj, indeks, start, długość)] — rodzaj: title | shot | end."""
    out, t = [("title", 0, 0.0, title_s)], title_s
    for i, d in enumerate(durations):
        out.append(("shot", i, round(t, 3), d))
        t += d
    out.append(("end", 0, round(t, 3), end_s))
    return out


def filter_path(path):
    """Ścieżka do opcji filtra ffmpeg (fontfile=, textfile=): ukośniki, `:` i `'` escapowane."""
    return "'" + path.replace("\\", "/").replace("'", r"\'").replace(":", r"\:") + "'"


def card_cmd(ffmpeg, out, seconds, size, font, lines):
    """Plansza: tło + do dwóch linii tekstu (tekst z plików UTF-8 — bez escapowania treści).
    lines: [(ścieżka_pliku_tekstu, wysokość_fontu_jako_ułamek_H, kolor, przesunięcie_y_jako_ułamek_H)]."""
    w, h = size.split("x")
    draws = []
    for textfile, rel, color, dy in lines:
        draws.append(f"drawtext=fontfile={filter_path(font)}:textfile={filter_path(textfile)}:expansion=none:"
                     f"fontcolor={color}:fontsize=h*{rel}:x=(w-text_w)/2:y=(h-text_h)/2+h*{dy}")
    vf = ",".join(draws + [f"fade=t=in:st=0:d=0.6,fade=t=out:st={max(seconds - 0.6, 0):.2f}:d=0.6"])
    return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c={CARD_BG}:s={w}x{h}:d={seconds}:r={FPS}",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-vf", vf, "-t", f"{seconds:.3f}", *VCODEC, *ACODEC, out]


def shot_cmd(ffmpeg, clip, audio, out, seconds, size):
    """Ujęcie: klip skalowany do rozmiaru filmu, ostatnia klatka trzymana (tpad), gdy klip krótszy
    od kwestii; głos znormalizowany (LOUDNESS) i dopełniony ciszą (apad); całość ucięta do długości kwestii."""
    w, h = size.split("x")
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
          f"fps={FPS},tpad=stop_mode=clone:stop_duration={seconds:.3f}")
    return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", clip, "-i", audio,
            "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, "-af", f"{LOUDNESS},apad", "-t", f"{seconds:.3f}",
            *VCODEC, *ACODEC, out]


def concat_cmd(ffmpeg, list_file, srt, out, music="", total_s=0.0):
    """Sklejenie odcinków + napisy. Z podkładem: muzyka zapętlona, ściszona, wygaszona na końcu i zmiksowana
    z głosem (normalize=0 — głos zostaje na swoim poziomie); obraz dalej bez ponownego kodowania."""
    head = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list_file,
            "-i", srt]
    tail = ["-c:s", "mov_text", "-metadata:s:s:0", "language=pol", "-movflags", "+faststart", out]
    if not music:
        return head + ["-map", "0:v", "-map", "0:a", "-map", "1:0", "-c:v", "copy", "-c:a", "copy"] + tail
    fade_at = max(total_s - MUSIC_FADE_S, 0)
    mix = (f"[2:a]volume={MUSIC_GAIN},afade=t=in:st=0:d=1,afade=t=out:st={fade_at:.3f}:d={MUSIC_FADE_S}[m];"
           "[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
    return head + ["-stream_loop", "-1", "-i", music, "-filter_complex", mix, "-map", "0:v", "-map", "[a]",
                   "-map", "1:0", "-c:v", "copy", *ACODEC, "-t", f"{total_s:.3f}"] + tail


def concat_list(paths):
    """Plik listy dla demuxera concat (apostrofy w ścieżkach escapowane)."""
    return "".join("file '{}'\n".format(p.replace("\\", "/").replace("'", r"'\''")) for p in paths)


def plan(manifest, workdir, ffmpeg, font, music=""):
    """Manifest z aplikacji + pobrane pliki w workdir → (pliki tekstowe do zapisania, komendy, wynik).
    Oczekuje w workdir: clip_<n>.mp4 i audio_<n>.mp3 dla każdego ujęcia (n od 0); music = podkład albo ""."""
    j = os.path.join
    size, files, cmds, parts = manifest["resolution"], {}, [], []
    files[j(workdir, "title.txt")] = manifest["title"]
    files[j(workdir, "subtitle.txt")] = manifest.get("subtitle", "")
    files[j(workdir, "end.txt")] = manifest.get("end_title", "")
    files[j(workdir, "subs.srt")] = manifest["srt"]
    tl = timeline(manifest["title_s"], [s["duration"] for s in manifest["shots"]], manifest["end_s"])
    for kind, i, _start, seconds in tl:
        if kind == "title":
            out = j(workdir, "part_title.mp4")
            cmds.append(card_cmd(ffmpeg, out, seconds, size, font, [
                (j(workdir, "title.txt"), 0.065, "white", -0.04), (j(workdir, "subtitle.txt"), 0.03, ACCENT, 0.06)]))
        elif kind == "shot":
            out = j(workdir, f"part_{i:03d}.mp4")
            cmds.append(shot_cmd(ffmpeg, j(workdir, f"clip_{i}.mp4"), j(workdir, f"audio_{i}.mp3"), out, seconds, size))
        else:
            out = j(workdir, "part_end.mp4")
            cmds.append(card_cmd(ffmpeg, out, seconds, size, font, [(j(workdir, "end.txt"), 0.05, "white", 0.0)]))
        parts.append(out)
    files[j(workdir, "parts.txt")] = concat_list(parts)
    final = j(workdir, "film.mp4")
    total = tl[-1][2] + tl[-1][3]
    cmds.append(concat_cmd(ffmpeg, j(workdir, "parts.txt"), j(workdir, "subs.srt"), final, music, total))
    return files, cmds, final
