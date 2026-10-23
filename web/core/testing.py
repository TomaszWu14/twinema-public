"""Runner testów: obowiązkowy TOTP Administratorów (US-017) wyłączony — testy logują konta przez force_login.
Bramka odwiedzających demo też jest wyłączona (`@override_settings(DEMO_VISITOR_GATE=True)`).
Testy drugiego składnika włączają go jawnie: `@override_settings(TWO_FACTOR_ADMIN=True)`."""

from django.conf import settings
from django.test.runner import DiscoverRunner


class TestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.TWO_FACTOR_ADMIN = False
        settings.DEMO_VISITOR_GATE = False
