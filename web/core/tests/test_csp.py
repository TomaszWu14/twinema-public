"""US-005: CSP wymuszana, skrypty tylko z serwera albo z jednorazowym nonce; bez obsługi zdarzeń w atrybutach."""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

INLINE_HANDLER = re.compile(r"<[^>]+\son(click|change|submit|load|input|keyup|keydown|focus|blur)\s*=", re.I)
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)(?![^>]*application/json)[^>]*>", re.I)


class CspHeaderTests(TestCase):
    def test_enforced_policy_with_fresh_nonce(self):
        a = self.client.get("/login/")
        b = self.client.get("/login/")
        policy = a["Content-Security-Policy"]
        self.assertNotIn("Content-Security-Policy-Report-Only", a)
        script_src = re.search(r"script-src ([^;]+)", policy).group(1)
        self.assertNotIn("'unsafe-inline'", script_src)
        self.assertNotIn("'unsafe-eval'", script_src)
        nonce = re.search(r"'nonce-([^']+)'", policy).group(1)
        self.assertNotEqual(nonce, re.search(r"'nonce-([^']+)'", b["Content-Security-Policy"]).group(1))
        self.assertIn("object-src 'none'", policy)

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_switch(self):
        r = self.client.get("/login/")
        self.assertIn("Content-Security-Policy-Report-Only", r)
        self.assertNotIn("Content-Security-Policy", r)


class TemplatesFollowCspTests(SimpleTestCase):
    def _templates(self):
        return list(Path(settings.BASE_DIR).glob("*/templates/**/*.html"))

    def test_no_inline_event_handlers(self):
        bad = [f"{p.relative_to(settings.BASE_DIR)}" for p in self._templates() if INLINE_HANDLER.search(p.read_text())]
        self.assertEqual(bad, [], "onclick=/onchange= blokuje CSP — użyj data-confirm / data-autosubmit (core/js/ui.js)")

    def test_inline_scripts_carry_nonce(self):
        bad = []
        for p in self._templates():
            for tag in INLINE_SCRIPT.findall(p.read_text()):
                if 'nonce="{{ csp_nonce }}"' not in tag:
                    bad.append(f"{p.relative_to(settings.BASE_DIR)}: {tag}")
        self.assertEqual(bad, [])


class InlineStylesDoNotGrowTests(SimpleTestCase):
    """T-17: style w szablonach (`style=`, `<style>`) wymagają 'unsafe-inline' w style-src. Do czasu przeniesienia
    ich do plików CSS liczba w żadnym szablonie nie może rosnąć — nowy kod używa klas z core/*.css.
    Po usunięciu stylów z szablonu zaktualizuj `inline_styles_baseline.json` (liczba może tylko maleć)."""

    def test_no_template_adds_inline_styles(self):
        import json
        baseline = json.loads((Path(__file__).parent / "inline_styles_baseline.json").read_text())
        grown = {}
        for p in Path(settings.BASE_DIR).glob("*/templates/**/*.html"):
            text = p.read_text()
            n = len(re.findall(r'\sstyle="', text)) + len(re.findall(r"<style\b", text))
            key = str(p.relative_to(settings.BASE_DIR))
            if n > baseline.get(key, 0):
                grown[key] = f"{baseline.get(key, 0)} → {n}"
        self.assertEqual(grown, {}, "Nowe style w szablonach — użyj klasy CSS (T-17)")
