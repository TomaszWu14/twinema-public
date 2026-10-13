"""Opis na YouTube: rozdziały z osi czasu montażu (zasady YouTube: od 00:00, ≥ 3, każdy ≥ 10 s)."""
from django.test import SimpleTestCase

from studio.youtube import chapters, description, label, stamp


class YoutubeTests(SimpleTestCase):
    def test_label_first_sentence_trimmed_on_word(self):
        self.assertEqual(label("Hala ma 118 regałów. Reszta zdania."), "Hala ma 118 regałów")
        long = "Na działce stoi hala z regałami wysokiego składowania i strefami specjalnymi dla towarów ADR oraz chłodni"
        out = label(long)
        self.assertTrue(out.endswith("…") and len(out) <= 61 and " " in out)

    def test_stamp(self):
        self.assertEqual((stamp(0), stamp(75.9), stamp(3725)), ("00:00", "01:15", "1:02:05"))

    def test_title_in_first_chapter_short_shots_merged_end_in_last(self):
        shots = [(12.0, "Działka."), (4.0, "Hala."), (8.0, "Strefy."), (15.0, "Doki."), (3.0, "Koniec.")]
        # 0–15 działka (z planszą 3 s), 15–19 hala (4 s → dokleja strefy: 12 s), 27–42 doki + 3 s + plansza końcowa
        self.assertEqual(chapters(3.0, shots, 3.0), [(0.0, "Działka"), (15.0, "Hala"), (27.0, "Doki")])

    def test_too_few_chapters_returns_empty(self):
        self.assertEqual(chapters(3.0, [(20.0, "A."), (20.0, "B.")], 3.0), [])

    def test_short_last_chapter_joins_previous(self):
        out = chapters(3.0, [(12.0, "A."), (12.0, "B."), (12.0, "C."), (2.0, "D.")], 3.0)
        self.assertEqual([lab for _t, lab in out], ["A", "B", "C"])         # D (2 s) + plansza 3 s < 10 s → do C

    def test_description_with_demo_link_and_chapters(self):
        text = description("Nowe centrum", [(0.0, "A"), (15.0, "B"), (30.0, "C")], demo_url="https://x/demo/")
        self.assertTrue(text.startswith("Nowe centrum\n"))
        self.assertIn("Wersja demo bez logowania: https://x/demo/", text)
        self.assertIn("Rozdziały:\n00:00 A\n00:15 B\n00:30 C\n", text)
