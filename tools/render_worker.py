"""Worker renderów TWINEMA — uruchamiany na komputerze z Blenderem (np. z GPU).

Odpytuje aplikację po HTTPS (wychodzące połączenia — serwer nie musi otwierać żadnych portów),
przejmuje zlecenie, pobiera scenę, renderuje `tools/blender/twinema_render.py` w Blenderze bez okna
i odsyła PNG/MP4. Gdy kolejka renderów pusta, a jest ffmpeg — montuje filmy ze Studia
(`twinema_montage.py`). Tylko biblioteka standardowa Pythona.

  set TWINEMA_URL=https://twinema.twapp.pl
  set TWINEMA_WORKER_TOKEN=<RENDER_WORKER_TOKEN z serwera>
  python tools/render_worker.py [--once] [--poll 10] [--blender "C:/.../blender.exe"] [--engine eevee]
"""
import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import twinema_montage as montage  # noqa: E402  (obok skryptu, uruchamianego jako plik)
RENDER_SCRIPT = os.path.join(HERE, "blender", "twinema_render.py")
TIMEOUT_S = 60 * 60                     # twardy limit jednego renderu


def find_blender(explicit=""):
    """BLENDER_BIN / --blender → PATH → typowe katalogi instalacji (najnowsza wersja)."""
    for cand in (explicit, os.environ.get("BLENDER_BIN", ""), shutil.which("blender") or ""):
        if cand and os.path.isfile(cand):
            return cand
    patterns = ["C:/Program Files/Blender Foundation/Blender */blender.exe",
                "/Applications/Blender.app/Contents/MacOS/Blender", "/usr/bin/blender", "/snap/bin/blender"]
    found = sorted(p for pat in patterns for p in glob.glob(pat))
    if not found:
        sys.exit("Nie znalazłem Blendera — podaj --blender albo ustaw BLENDER_BIN.")
    return found[-1]


class Api:
    def __init__(self, base, token, name):
        self.base, self.token, self.name = base.rstrip("/"), token, name

    def _req(self, url, data=None, headers=None, method=None):
        h = {"X-Worker-Token": self.token, "User-Agent": f"twinema-worker/{self.name}", **(headers or {})}
        req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data is not None else "GET"))
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, resp.read()

    def claim(self, path="/api/render/claim/"):
        status, body = self._req(f"{self.base}{path}", data=f"worker={self.name}".encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
        return json.loads(body) if status == 200 else None

    def get(self, url, claim):
        return self._req(url, headers={"X-Claim": claim})[1]

    def post_form(self, url, claim, fields, file_path=None, ctype="application/octet-stream"):
        boundary = uuid.uuid4().hex
        parts = []
        for k, v in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        if file_path:
            name = os.path.basename(file_path)
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                         f"Content-Type: {ctype}\r\n\r\n".encode())
            with open(file_path, "rb") as fh:
                parts.append(fh.read())
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return self._req(url, data=b"".join(parts), headers={
            "X-Claim": claim, "Content-Type": f"multipart/form-data; boundary={boundary}"})


def run_job(api, job, blender, engine, samples):
    print(f"[{time.strftime('%H:%M:%S')}] Zlecenie {job['id']}: {job['title']} ({job['preset']}, {job['resolution']})")
    with tempfile.TemporaryDirectory(prefix="twinema_") as tmp:
        scene_path = os.path.join(tmp, "scena.json")
        out = os.path.join(tmp, f"render.{job['ext']}")
        with open(scene_path, "wb") as fh:
            fh.write(api.get(job["scene_url"], job["claim"]))
        cmd = [blender, "-b", "--factory-startup", "-P", RENDER_SCRIPT, "--", scene_path, out,
               "--preset", job["preset"], "--seconds", str(job["seconds"]), "--res", job["resolution"],
               "--engine", engine, "--samples", str(samples)]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=TIMEOUT_S)
            log = (proc.stdout or "")[-8000:] + (proc.stderr or "")[-4000:]
            ok = proc.returncode == 0 and os.path.isfile(out) and "TWINEMA_RENDER_OK" in proc.stdout
        except subprocess.TimeoutExpired:
            ok, log = False, f"Przekroczony limit {TIMEOUT_S // 60} min renderu."
        took = round(time.time() - t0)
        if not ok:
            print(f"  ✗ błąd po {took} s — wysyłam log")
            api.post_form(job["fail_url"], job["claim"], {"error": log or "Blender zakończył się bez wyniku."})
            return False
        ctype = "video/mp4" if job["ext"] == "mp4" else "image/png"
        api.post_form(job["result_url"], job["claim"], {"log": f"render {took} s\n" + log[-4000:]}, out, ctype)
        print(f"  ✓ gotowe w {took} s ({os.path.getsize(out) // 1024} KB)")
        return True


def run_montage(api, job, ffmpeg, font, music=""):
    """Montaż filmu: pobierz ujęcia i nagrania, wykonaj komendy z twinema_montage.plan, wyślij MP4."""
    print(f"[{time.strftime('%H:%M:%S')}] Montaż {job['id']}: {job['title']} ({len(job['shots'])} ujęć)")
    with tempfile.TemporaryDirectory(prefix="twinema_film_") as tmp:
        t0, log = time.time(), []
        try:
            for i, s in enumerate(job["shots"]):
                for url, name in ((s["clip_url"], f"clip_{i}.mp4"), (s["audio_url"], f"audio_{i}.mp3")):
                    with open(os.path.join(tmp, name), "wb") as fh:
                        fh.write(api.get(url, job["claim"]))
            files, cmds, final = montage.plan(job, tmp, ffmpeg, font, music)
            for path, text in files.items():
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
            for cmd in cmds:
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      timeout=TIMEOUT_S)
                log.append(" ".join(cmd[-1:]) + ": " + (proc.stderr or "ok")[-1500:])
                if proc.returncode != 0:
                    raise RuntimeError(f"ffmpeg zakończył się kodem {proc.returncode}")
        except (RuntimeError, OSError, subprocess.TimeoutExpired, urllib.error.URLError) as exc:
            print(f"  ✗ montaż nieudany: {exc}")
            api.post_form(job["fail_url"], job["claim"], {"error": f"{exc}\n" + "\n".join(log)[-8000:]})
            return False
        api.post_form(job["result_url"], job["claim"], {"log": f"montaż {round(time.time() - t0)} s"},
                      final, "video/mp4")
        print(f"  ✓ film gotowy ({os.path.getsize(final) // 1024} KB)")
        return True


def main():
    p = argparse.ArgumentParser(description="Worker renderów TWINEMA (Blender bez okna)")
    p.add_argument("--url", default=os.environ.get("TWINEMA_URL", "http://localhost:8090"))
    p.add_argument("--token", default=os.environ.get("TWINEMA_WORKER_TOKEN", ""))
    p.add_argument("--blender", default="")
    p.add_argument("--engine", default="eevee", choices=["eevee", "cycles", "workbench"])
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--poll", type=int, default=10, help="co ile sekund pytać o zlecenia")
    p.add_argument("--once", action="store_true", help="jedno zlecenie (albo brak) i koniec")
    p.add_argument("--ffmpeg", default="", help="ścieżka ffmpeg do montażu (inaczej FFMPEG_BIN / PATH / winget)")
    p.add_argument("--font", default="", help="font TTF plansz z polskimi znakami (inaczej TWINEMA_FONT / systemowy)")
    p.add_argument("--music", default="", help="podkład muzyczny filmu (mp3/wav, inaczej TWINEMA_MUSIC); brak = bez muzyki")
    a = p.parse_args()
    if len(a.token) < 32:
        sys.exit("Brak tokenu: ustaw TWINEMA_WORKER_TOKEN (ten sam co RENDER_WORKER_TOKEN na serwerze).")
    blender = find_blender(a.blender)
    ffmpeg, font, music = montage.find_ffmpeg(a.ffmpeg), montage.find_font(a.font), montage.find_music(a.music)
    api = Api(a.url, a.token, platform.node()[:40] or "worker")
    print(f"TWINEMA worker → {a.url} | Blender: {blender} | silnik: {a.engine}")
    if music:
        print(f"Podkład muzyczny filmów: {music}")
    if not (ffmpeg and font):
        print("Montaż filmów wyłączony — brak ffmpeg (FFMPEG_BIN / winget install Gyan.FFmpeg) "
              "albo fontu (TWINEMA_FONT). Rendery działają normalnie.")
    while True:
        try:
            job = api.claim()
            if job:
                run_job(api, job, blender, a.engine, a.samples)
            elif ffmpeg and font and (job := api.claim("/api/studio/montage/claim/")):
                run_montage(api, job, ffmpeg, font, music)
            if job:
                if a.once:
                    return
                continue                       # od razu następne zlecenie
        except urllib.error.HTTPError as exc:
            print(f"Serwer odpowiedział {exc.code}: {exc.read()[:300]!r}")
            if exc.code == 403:
                sys.exit("Zły token albo API workera wyłączone na serwerze.")
        except (urllib.error.URLError, OSError) as exc:
            print(f"Brak połączenia ({exc}) — ponowię za {a.poll} s")
        if a.once:
            return
        time.sleep(a.poll)


if __name__ == "__main__":
    main()
