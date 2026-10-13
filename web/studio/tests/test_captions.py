"""Czysta logika napisów: długość ujęcia z tekstu, rozkład słów w czasie, plansze, SRT."""
from unittest import TestCase

from studio.captions import (LEAD_S, LINE_CHARS, MAX_SHOT_S, MIN_SHOT_S, TAIL_S, build_srt, cues, offsets,
                             shot_cues, shot_seconds, srt_time, timed_words)


class ShotSecondsTests(TestCase):
    def test_reading_time_with_bounds(self):
        self.assertEqual(shot_seconds("Krótko."), MIN_SHOT_S)
        self.assertEqual(shot_seconds(" ".join(["słowo"] * 22)), 11.5)          # 22 / 2,2 + 1,5
        self.assertEqual(shot_seconds(" ".join(["słowo"] * 500)), MAX_SHOT_S)
        self.assertEqual(shot_seconds("  "), MIN_SHOT_S)


class TimedWordsTests(TestCase):
    def test_words_fill_shot_in_order(self):
        tw = timed_words("Ala  ma kota.", 5.0)
        self.assertEqual([w for w, _, _ in tw], ["Ala", "ma", "kota."])
        self.assertEqual(tw[0][1], LEAD_S)
        self.assertAlmostEqual(tw[-1][2], 5.0 - TAIL_S, places=2)
        self.assertTrue(all(a[2] <= b[1] + 1e-6 for a, b in zip(tw, tw[1:], strict=False)))
        self.assertGreater(tw[2][2] - tw[2][1], tw[1][2] - tw[1][1])           # dłuższe słowo dłużej
        self.assertEqual(timed_words("", 5.0), [])


class CueTests(TestCase):
    def test_lines_never_exceed_limits(self):
        text = ("Hala ma 2 300 miejsc paletowych na czterech poziomach regałów. "
                "Średnia droga do miejsca to 40 m, a do strefy A 20 m. "
                "Cztery roboty obsługują kompletację.")
        secs = shot_seconds(text)
        cs = shot_cues(text, secs)
        self.assertGreater(len(cs), 2)
        for start, end, t in cs:
            lines = t.split("\n")
            self.assertLessEqual(len(lines), 2)
            self.assertTrue(all(len(x) <= LINE_CHARS for x in lines))
            self.assertLessEqual(end - start, 6.0 + 1.0)
            self.assertLessEqual(end, secs)
        self.assertEqual(" ".join(t.replace("\n", " ") for _, _, t in cs), text)   # nic nie zginęło
        self.assertEqual([c[0] for c in cs], sorted(c[0] for c in cs))

    def test_short_text_single_cue(self):
        self.assertEqual(shot_cues("Krótko.", 5.0), [(LEAD_S, 4.4, "Krótko.")])
        self.assertEqual(cues([]), [])


class SrtTests(TestCase):
    def test_time_format(self):
        self.assertEqual(srt_time(0), "00:00:00,000")
        self.assertEqual(srt_time(3725.4567), "01:02:05,457")

    def test_build_with_offsets(self):
        srt = build_srt([(0, [(0.0, 1.5, "Pierwsza.")]), (10.0, [(0.2, 2.0, "Druga\nlinia.")])])
        self.assertEqual(srt, "1\n00:00:00,000 --> 00:00:01,500\nPierwsza.\n\n"
                              "2\n00:00:10,200 --> 00:00:12,000\nDruga\nlinia.\n")

    def test_offsets(self):
        self.assertEqual(offsets([2.0, 3.5, 1.0]), [0.0, 2.0, 5.5])
        self.assertEqual(offsets([2.0, 3.0], gap_s=0.5, start_s=4.0), [4.0, 6.5])
