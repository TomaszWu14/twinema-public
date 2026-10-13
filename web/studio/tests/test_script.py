"""Czysta logika scenariusza: fakty z KPI, szablon, walidacja szkicu, szacunek długości."""
from unittest import TestCase

from studio.script import (MAX_SHOT_CHARS, MAX_SHOTS, PRESETS, clean_draft, kpi_facts,
                           template_script)

KPI = {"pallet_positions": 2304, "positions_per_m2": 0.768, "built_area_m2": 1210.5, "floor_area_m2": 3000.0,
       "travel": {"avg_m": 41.27, "a_zone_avg_m": 18.0, "max_m": 80.0, "anchors": 2},
       "equipment": {"amr": {"label": "Robot AMR", "count": 4, "throughput_h": 240}},
       "aisle_issue_count": 0, "by_kind": {}}


class KpiFactsTests(TestCase):
    def test_numbers_in_polish_format(self):
        text = " ".join(kpi_facts(KPI))
        self.assertIn("Miejsca paletowe: 2 304 (0,77 na m² hali).", text)
        self.assertIn("Średnia droga do miejsca paletowego: 41,3 m.", text)
        self.assertIn("Robot AMR: 4 szt., nominalnie 240 na godzinę.", text)
        self.assertIn("Alejki bez naruszeń", text)

    def test_missing_values_are_skipped_not_guessed(self):
        self.assertEqual(kpi_facts({}), [])
        facts = kpi_facts({"pallet_positions": 10, "travel": {"avg_m": None}, "aisle_issue_count": 3})
        self.assertEqual(facts, ["Miejsca paletowe: 10.", "Naruszenia alejek do poprawy: 3."])


class TemplateScriptTests(TestCase):
    def test_template_uses_kpi_and_valid_presets(self):
        shots = template_script(KPI)
        self.assertEqual(len(shots), 5)
        self.assertTrue(all(s["preset"] in PRESETS and s["text"] for s in shots))
        self.assertIn("2 304", shots[1]["text"])

    def test_template_works_without_kpi(self):
        self.assertTrue(all(s["text"] for s in template_script({})))


class CleanDraftTests(TestCase):
    def test_fixes_presets_skips_empty_and_normalises_spaces(self):
        shots, warnings = clean_draft([{"preset": "orbita", "text": "  Hala\n z  góry. "},
                                       {"preset": "dron", "text": "Coś."}, {"preset": "plan", "text": "  "}])
        self.assertEqual(shots, [{"preset": "orbita", "text": "Hala z góry."}, {"preset": "ogolny", "text": "Coś."}])
        self.assertEqual(len(warnings), 2)

    def test_cuts_long_text_at_sentence_and_caps_count(self):
        long = "Zdanie numer jeden. " * 60
        shots, _ = clean_draft([{"preset": "plan", "text": long}] * (MAX_SHOTS + 3))
        self.assertEqual(len(shots), MAX_SHOTS)
        self.assertLessEqual(len(shots[0]["text"]), MAX_SHOT_CHARS)
        self.assertTrue(shots[0]["text"].endswith("."))

    def test_garbage_input(self):
        self.assertEqual(clean_draft(None), ([], []))
        self.assertEqual(clean_draft([None])[0], [])

