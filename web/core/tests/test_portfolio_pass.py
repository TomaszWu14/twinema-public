"""Przepustka z portfolio (ciasteczko `gosc`): ważna → bez formularza bramki i bez własnego pusha; reszta → formularz."""
import urllib.error
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from core import demo_gate
from core.models import DemoVisitor
from core.roles import GROUP_VIEWER

URLOPEN = "core.demo_gate.urllib.request.OpenerDirector.open"


def _resp(status):
    r = mock.MagicMock()
    r.status = status
    r.__enter__.return_value = r
    return r


@override_settings(DEMO_PUBLIC=True, DEMO_VISITOR_GATE=True, PORTFOLIO_PASS=True,
                   PORTFOLIO_URL="https://portfolio.example")
class PortfolioPassTests(TestCase):
    def setUp(self):
        demo_gate._pass_cache.clear()
        User.objects.create_user("demo").groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.client.cookies["gosc"] = "tok-123"

    def test_valid_pass_skips_form_and_enters_without_push(self):
        with mock.patch(URLOPEN, return_value=_resp(200)) as op, \
                mock.patch("core.visitor_notify.notify") as notify:
            page = self.client.get(reverse("core:demo"))
            self.assertNotContains(page, "przedstaw się, proszę.")
            self.assertContains(page, "Wejdź do systemu")
            r = self.client.post(reverse("core:demo_enter"))
        self.assertRedirects(r, reverse("core:home"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)
        notify.assert_not_called()
        v = DemoVisitor.objects.get()
        self.assertEqual(v.first_name, "Gość z portfolio")
        req = op.call_args.args[0]
        self.assertEqual(req.full_url, "https://portfolio.example/api/gosc")
        self.assertEqual(req.get_header("Cookie"), "gosc=tok-123")
        self.assertEqual(op.call_args.kwargs["timeout"], 2)

    def test_positive_result_cached(self):
        with mock.patch(URLOPEN, return_value=_resp(200)) as op:
            self.client.get(reverse("core:demo"))
            self.client.get(reverse("core:demo"))
        self.assertEqual(op.call_count, 1)

    def test_401_shows_form(self):
        err = urllib.error.HTTPError("u", 401, "no", {}, None)
        with mock.patch(URLOPEN, side_effect=err):
            self.assertContains(self.client.get(reverse("core:demo")), "przedstaw się, proszę.")
            r = self.client.post(reverse("core:demo_enter"))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(DemoVisitor.objects.count(), 0)

    def test_non_200_or_redirect_shows_form(self):
        with mock.patch(URLOPEN, return_value=_resp(204)):
            self.assertContains(self.client.get(reverse("core:demo")), "przedstaw się, proszę.")

    def test_timeout_shows_form(self):
        with mock.patch(URLOPEN, side_effect=TimeoutError):
            r = self.client.get(reverse("core:demo"))
        self.assertContains(r, "przedstaw się, proszę.")

    def test_no_cookie_no_network(self):
        self.client.cookies.clear()
        with mock.patch(URLOPEN) as op:
            self.assertContains(self.client.get(reverse("core:demo")), "przedstaw się, proszę.")
        op.assert_not_called()

    def test_oversized_cookie_no_network(self):
        self.client.cookies["gosc"] = "x" * 201
        with mock.patch(URLOPEN) as op:
            self.client.get(reverse("core:demo"))
        op.assert_not_called()

    def test_disabled_or_insecure_url_no_network(self):
        for cfg in ({"PORTFOLIO_PASS": False}, {"PORTFOLIO_URL": "http://portfolio.example"}):
            with override_settings(**cfg), mock.patch(URLOPEN) as op:
                self.assertContains(self.client.get(reverse("core:demo")), "przedstaw się, proszę.")
            op.assert_not_called()
