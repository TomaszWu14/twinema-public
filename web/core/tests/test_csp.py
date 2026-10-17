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
        style_src = re.search(r"style-src ([^;]+)", policy).group(1)
        self.assertNotIn("'unsafe-inline'", style_src)                    # R-20
        self.assertIn("'nonce-", style_src)
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


class InlineStylesTests(SimpleTestCase):
    """R-20: CSP bez 'unsafe-inline' w style-src blokuje atrybuty style= (także wstawiane przez innerHTML
    i setAttribute) oraz <style> bez nonce. Wygląd — klasy z core/utilities.css i plików CSS; wartości z danych —
    data-pct / data-color (core/js/ui.js); z JS — el.style (CSSOM), którego CSP nie blokuje."""

    STYLE_ATTR = re.compile(r"""\sstyle\s*=\s*["'`]""")

    def test_templates_have_no_style_attributes(self):
        bad = [f"{p.relative_to(settings.BASE_DIR)}:{n}" for p in Path(settings.BASE_DIR).glob("*/templates/**/*.html")
               for n, line in enumerate(p.read_text().splitlines(), 1) if self.STYLE_ATTR.search(line)]
        self.assertEqual(bad, [], "Atrybut style= blokuje CSP — użyj klasy (core/utilities.css) albo data-pct/data-color")

    def test_style_blocks_carry_nonce(self):
        bad = [f"{p.relative_to(settings.BASE_DIR)}: {tag}" for p in Path(settings.BASE_DIR).glob("*/templates/**/*.html")
               for tag in re.findall(r"<style\b[^>]*>", p.read_text()) if 'nonce="{{ csp_nonce }}"' not in tag]
        self.assertEqual(bad, [])

    def test_own_scripts_do_not_write_style_attributes(self):
        pattern = re.compile(r"""\sstyle=["'`$]|setAttribute\(\s*["']style""")
        bad = [f"{p.relative_to(settings.BASE_DIR)}:{n}" for p in Path(settings.BASE_DIR).glob("*/static/*/js/*.js")
               for n, line in enumerate(p.read_text().splitlines(), 1) if pattern.search(line)]
        self.assertEqual(bad, [], "Styl z JS ustawiaj przez el.style / el.style.cssText (CSSOM)")
