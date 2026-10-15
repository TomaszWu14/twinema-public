"""SEC: worker wysyła token w nagłówku — poza własnym komputerem tylko po HTTPS (tools/render_worker.check_url)."""
import sys
from unittest import TestCase

from django.conf import settings

sys.path.insert(0, str(settings.BASE_DIR.parent / "tools"))
import render_worker as w  # noqa: E402


class WorkerUrlTests(TestCase):
    def test_https_and_loopback_allowed(self):
        for url in ("https://example.test", "https://example.test/api/render/claim/", "http://localhost:8090",
                    "http://127.0.0.1:8000/x"):
            self.assertIsNone(w.check_url(url), url)

    def test_plain_http_to_remote_host_refused(self):
        self.assertIn("bez HTTPS", w.check_url("http://example.test"))

    def test_other_schemes_refused(self):
        for url in ("file:///etc/passwd", "ftp://example.test", "example.test"):
            self.assertIn("Nieprawidłowy adres", w.check_url(url), url)

    def test_request_to_insecure_url_raises_before_sending(self):
        api = w.Api("https://example.test", "t" * 32, "test")
        with self.assertRaises(w.urllib.error.URLError):
            api._req("http://example.test/scene.json")
