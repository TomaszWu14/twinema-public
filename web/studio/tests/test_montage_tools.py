"""tools/twinema_montage.py — oś czasu i kształt komend ffmpeg (bez uruchamiania ffmpeg)."""
import os
import sys
import tempfile
from unittest import TestCase, mock

from django.conf import settings

sys.path.insert(0, str(settings.BASE_DIR.parent / "tools"))
import twinema_montage as m  # noqa: E402

MANIFEST = {"title": "Nowe centrum — 100% gotowe", "subtitle": "TWINEMA", "end_title": "TWINEMA",
            "resolution": "1920x1080", "title_s": 3.0, "end_s": 3.0,
            "shots": [{"duration": 4.25, "captions": [[0.4, 2.0, "Hala z góry."], [2.0, 3.65, "Druga\nlinia."]]},
                      {"duration": 6.0, "captions": []}]}


class TimelineTests(TestCase):
    def test_title_shots_end(self):
        self.assertEqual(m.timeline(3.0, [4.25, 6.0], 3.0), [
            ("title", 0, 0.0, 3.0), ("shot", 0, 3.0, 4.25), ("shot", 1, 7.25, 6.0), ("end", 0, 13.25, 3.0)])


class EscapingTests(TestCase):
    def test_filter_path_windows(self):
        self.assertEqual(m.filter_path(r"C:\Windows\Fonts\segoeui.ttf"), r"'C\:/Windows/Fonts/segoeui.ttf'")
        self.assertEqual(m.filter_path("/tmp/it's.txt"), r"'/tmp/it\'s.txt'")

    def test_concat_list_quotes(self):
        self.assertEqual(m.concat_list([r"C:\t\a.mp4", "/x/it's.mp4"]),
                         "file 'C:/t/a.mp4'\nfile '/x/it'\\''s.mp4'\n")


class CommandTests(TestCase):
    def test_shot_holds_last_frame_silent_audio_and_cuts_to_length(self):
        cmd = m.shot_cmd("ffmpeg", "c.mp4", "o.mp4", 4.25, "1920x1080")
        vf = cmd[cmd.index("-vf") + 1]
        self.assertIn("tpad=stop_mode=clone:stop_duration=4.250", vf)
        self.assertIn("scale=1920:1080", vf)
        self.assertNotIn("drawtext", vf)
        self.assertIn("anullsrc=r=44100:cl=stereo", cmd)                      # bez lektora — cisza
        self.assertNotIn("-af", cmd)
        self.assertEqual(cmd[cmd.index("-t") + 1], "4.250")
        self.assertIn("yuv420p", cmd)
        self.assertEqual(cmd[-1], "o.mp4")

    def test_shot_burns_captions_with_timing(self):
        cmd = m.shot_cmd("ffmpeg", "c.mp4", "o.mp4", 4.25, "1920x1080", "C:/F/f.ttf",
                         [("C:/w/cap_0.txt", 0.4, 2.0), ("C:/w/cap_1.txt", 2.0, 3.65)])
        vf = cmd[cmd.index("-vf") + 1]
        self.assertEqual(vf.count("drawtext="), 2)
        self.assertIn(r"fontfile='C\:/F/f.ttf':textfile='C\:/w/cap_0.txt':expansion=none", vf)
        self.assertIn("enable='between(t,0.400,2.000)'", vf)
        self.assertIn("fontsize=45:", vf)                                      # 1080 × 0,042
        self.assertIn("box=1:boxcolor=black@0.6:boxborderw=17:", vf)
        self.assertLess(vf.index("tpad"), vf.index("drawtext"))                # napis także na trzymanej klatce

    def test_card_uses_textfile_without_expansion(self):
        cmd = m.card_cmd("ffmpeg", "t.mp4", 3.0, "1280x720", "C:/F/f.ttf", [("C:/w/title.txt", 0.06, "white", 0)])
        vf = cmd[cmd.index("-vf") + 1]
        self.assertIn(r"fontfile='C\:/F/f.ttf':textfile='C\:/w/title.txt':expansion=none", vf)
        self.assertIn("color=c=0x0f1115:s=1280x720:d=3.0:r=25", cmd)
        self.assertIn("anullsrc=r=44100:cl=stereo", cmd)

    def test_plan_builds_all_parts_and_caption_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            files, cmds, final = m.plan(MANIFEST, tmp, "ffmpeg", "font.ttf")
        self.assertEqual(len(cmds), 5)                         # tytuł, 2 ujęcia, koniec, concat
        self.assertEqual(final, os.path.join(tmp, "film.mp4"))
        self.assertEqual(files[os.path.join(tmp, "title.txt")], MANIFEST["title"])   # tekst w pliku, nie w filtrze
        self.assertEqual(files[os.path.join(tmp, "cap_000_01.txt")], "Druga\nlinia.")
        self.assertEqual(sum(1 for f in files if os.path.basename(f).startswith("cap_")), 2)
        self.assertEqual(files[os.path.join(tmp, "parts.txt")].count("file '"), 4)
        self.assertEqual(cmds[1][cmds[1].index("-vf") + 1].count("drawtext="), 2)
        self.assertNotIn("drawtext", cmds[2][cmds[2].index("-vf") + 1])      # ujęcie bez napisów
        concat = cmds[-1]
        self.assertIn("+faststart", concat)
        self.assertNotIn("mov_text", concat)                   # napisy są w obrazie
        self.assertEqual(concat[-1], final)
        self.assertTrue(all(isinstance(c, list) and all(isinstance(x, str) for x in c) for c in cmds))

    def test_plan_with_music_replaces_silence_and_keeps_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            _files, cmds, _final = m.plan(MANIFEST, tmp, "ffmpeg", "font.ttf", music="C:/m/podklad.mp3")
        concat = cmds[-1]
        self.assertEqual(concat[concat.index("C:/m/podklad.mp3") - 3:concat.index("C:/m/podklad.mp3")],
                         ["-stream_loop", "-1", "-i"])                     # zapętlona pod całym filmem
        af = concat[concat.index("-filter_complex") + 1]
        self.assertTrue(af.startswith(f"[1:a]{m.LOUDNESS},"))               # muzyka na poziomie YouTube
        self.assertIn("afade=t=out:st=13.750:d=2.5", af)                     # 16,25 s filmu − wygaszenie
        self.assertEqual(concat[concat.index("-c:v") + 1], "copy")
        self.assertEqual(concat[concat.index("-t") + 1], "16.250")

    def test_plan_without_music_copies_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            _files, cmds, _final = m.plan(MANIFEST, tmp, "ffmpeg", "font.ttf")
        self.assertNotIn("-filter_complex", cmds[-1])
        self.assertEqual(cmds[-1][cmds[-1].index("-c:a") + 1], "copy")


class FindTests(TestCase):
    def test_music_from_env_or_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fh:
            path = fh.name
        try:
            with mock.patch.dict(os.environ, {"TWINEMA_MUSIC": path}):
                self.assertEqual(m.find_music(), path)
            with mock.patch.dict(os.environ, {"TWINEMA_MUSIC": "/nie/ma.mp3"}):
                self.assertEqual(m.find_music(), "")
        finally:
            os.unlink(path)

    def test_env_overrides_and_missing_returns_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as fh:
            path = fh.name
        try:
            with mock.patch.dict(os.environ, {"FFMPEG_BIN": path, "TWINEMA_FONT": path}):
                self.assertEqual(m.find_ffmpeg(), path)
                self.assertEqual(m.find_font(), path)
        finally:
            os.unlink(path)
        with mock.patch.dict(os.environ, {"FFMPEG_BIN": "", "LOCALAPPDATA": "/nie/ma"}), \
                mock.patch("shutil.which", return_value=None):
            self.assertEqual(m.find_ffmpeg(), "")
