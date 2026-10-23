"""Powiadomienie push (ntfy) o nowym odwiedzającym demo: tylko po udanym zapisie, w tle, bez wpływu na gościa."""
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core import visitor_notify
from core.models import DemoVisitor
from core.roles import GROUP_VIEWER

OK = {"first_name": "Jan", "last_name": "Żółć", "company": "ACME", "gdpr": "1"}
URL = "https://ntfy.example.com/tajny-temat"


class _SyncThread:
    """Zamiast wątku w tle — uruchomienie od razu, żeby test widział wywołanie."""
    def __init__(self, target, args=(), **kwargs):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@override_settings(DEMO_PUBLIC=True, DEMO_VISITOR_GATE=True, NTFY_URL=URL, NTFY_TOKEN="")
@mock.patch("core.visitor_notify.threading.Thread", _SyncThread)
@mock.patch("core.visitor_notify.urllib.request.urlopen")
class VisitorNotifyTests(TestCase):
    def setUp(self):
        demo = User.objects.create_user("demo")
        demo.groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.url = reverse("core:demo_enter")

    def _sent(self, urlopen):
        self.assertEqual(urlopen.call_count, 1)
        req = urlopen.call_args.args[0]
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)
        return req

    def test_valid_form_sends_one_notification(self, urlopen):
        r = self.client.post(self.url, OK)
        self.assertRedirects(r, reverse("core:home"))
        req = self._sent(urlopen)
        self.assertEqual((req.full_url, req.get_method()), (URL, "POST"))
        self.assertEqual(req.data.decode("utf-8"), "Jan Żółć (ACME) wszedł do twinema")
        headers = dict(req.header_items())
        self.assertEqual(headers["Title"], "Nowy gosc: twinema")
        self.assertEqual((headers["Tags"], headers["Priority"]), ("bell", "high"))
        self.assertNotIn("Authorization", headers)
        for value in headers.values():
            value.encode("ascii")

    @override_settings(NTFY_TOKEN="tk_sekret")
    def test_token_adds_authorization(self, urlopen):
        self.client.post(self.url, OK)
        self.assertEqual(self._sent(urlopen).get_header("Authorization"), "Bearer tk_sekret")

    def test_honeypot_and_invalid_data_send_nothing(self, urlopen):
        self.client.post(self.url, OK | {"website": "http://spam"})
        self.client.post(self.url, OK | {"company": "x"})
        self.client.post(self.url, {k: v for k, v in OK.items() if k != "gdpr"})
        urlopen.assert_not_called()
        self.assertEqual(DemoVisitor.objects.count(), 0)

    @override_settings(NTFY_URL="")
    def test_without_url_no_network(self, urlopen):
        self.assertRedirects(self.client.post(self.url, OK), reverse("core:home"))
        urlopen.assert_not_called()
        self.assertEqual(DemoVisitor.objects.count(), 1)

    def test_send_error_does_not_affect_visitor(self, urlopen):
        urlopen.side_effect = OSError("ntfy niedostępny")
        with self.assertLogs("core.visitor_notify", "WARNING"):
            r = self.client.post(self.url, OK)
        self.assertRedirects(r, reverse("core:home"))
        self.assertEqual(DemoVisitor.objects.count(), 1)
        self.assertIn("_auth_user_id", self.client.session)

    @override_settings(NTFY_URL="file:///etc/passwd")
    def test_non_http_url_skipped_with_warning(self, urlopen):
        with self.assertLogs("core.visitor_notify", "WARNING"):
            self.assertRedirects(self.client.post(self.url, OK), reverse("core:home"))
        urlopen.assert_not_called()

    @override_settings(NTFY_WATCH_COMPANIES="  przyklad , firma-x ")
    def test_watched_company_sends_urgent(self, urlopen):
        self.client.post(self.url, OK | {"company": "PRZYKŁAD Sp. z o.o."})
        req = self._sent(urlopen)
        headers = dict(req.header_items())
        self.assertEqual((headers["Priority"], headers["Tags"]), ("urgent", "rotating_light"))
        self.assertEqual(headers["Title"], "UWAGA firma z listy: twinema")
        self.assertEqual(req.data.decode("utf-8"), "⚠️ Jan Żółć (PRZYKŁAD Sp. z o.o.) wszedł do twinema")
        for value in headers.values():
            value.encode("ascii")

    @override_settings(NTFY_WATCH_COMPANIES="przyklad, x")
    def test_unwatched_company_sends_normal(self, urlopen):
        self.client.post(self.url, OK)          # „ACME” nie zawiera „przyklad”; jednoznakowa fraza „x” pominięta
        headers = dict(self._sent(urlopen).header_items())
        self.assertEqual((headers["Priority"], headers["Tags"], headers["Title"]), ("high", "bell", "Nowy gosc: twinema"))

    @override_settings(NTFY_WATCH_COMPANIES=" , ,")
    def test_empty_watch_list_sends_normal(self, urlopen):
        self.client.post(self.url, OK)
        self.assertEqual(dict(self._sent(urlopen).header_items())["Priority"], "high")

    def test_body_capped_at_300_chars(self, urlopen):
        req = visitor_notify.build_request({"first_name": "A" * 200, "last_name": "B" * 200, "company": "C"})
        self.assertEqual(len(req.data.decode("utf-8")), 300)
        urlopen.assert_not_called()


class WatchMatchTests(SimpleTestCase):
    @override_settings(NTFY_WATCH_COMPANIES="acme")
    def test_diacritics_and_case(self):
        self.assertTrue(visitor_notify.watched("ÄCME sp. z o.o."))
        self.assertTrue(visitor_notify.watched("Grupa   acme  "))
        self.assertFalse(visitor_notify.watched("ACM E"))

    @override_settings(NTFY_WATCH_COMPANIES="łódzka  fabryka")
    def test_phrase_normalized_too(self):
        self.assertTrue(visitor_notify.watched("LODZKA FABRYKA Sp. j."))

    @override_settings(NTFY_WATCH_COMPANIES="")
    def test_empty_list_never_matches(self):
        self.assertFalse(visitor_notify.watched("ACME"))


@override_settings(DEMO_PUBLIC=True, DEMO_VISITOR_GATE=True)
class ClauseTests(TestCase):
    def test_clause_mentions_ntfy(self):
        r = self.client.get(reverse("core:demo"))
        self.assertContains(r, "Dane przechowuję 90 dni, potem są automatycznie usuwane. O każdej wizycie (imię, "
                               "nazwisko, firma) dostaję powiadomienie na telefon przez usługę powiadomień push ntfy. "
                               "Zapisuję też, ile i jakie ekrany wersji demonstracyjnej obejrzałeś (bez adresu IP), "
                               "żeby wiedzieć, co zainteresowało gości. Poza tym nikomu danych nie przekazuję.")
        self.assertNotContains(r, "i nikomu ich nie przekazuję")
        self.assertNotContains(r, "push ntfy; poza tym")
