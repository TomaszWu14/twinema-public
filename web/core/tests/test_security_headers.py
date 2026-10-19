"""Nagłówki bezpieczeństwa na każdej odpowiedzi (HTML i JSON); CSP sprawdza osobno test_csp.py (US-005)."""
from django.test import TestCase


class SecurityHeadersTests(TestCase):
    def _assert_common(self, response):
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn(response["Referrer-Policy"], ("same-origin", "strict-origin-when-cross-origin"))
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")
        policy = response["Permissions-Policy"]
        for feature in ("camera", "geolocation", "microphone", "payment", "usb"):
            self.assertIn(f"{feature}=()", policy)

    def test_html_page(self):
        r = self.client.get("/login/")
        self.assertEqual(r.status_code, 200)
        self._assert_common(r)

    def test_json_api_is_not_cached(self):
        r = self.client.get("/health/")
        self.assertTrue(r["Content-Type"].startswith("application/json"))
        self._assert_common(r)
        self.assertIn("no-store", r["Cache-Control"])
