"""Aktywność gościa demo (RODO CP-7): liczone tylko udane strony HTML od gościa z ciasteczkiem z id wpisu."""
from unittest import mock

from django.contrib.auth.models import Group, User
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core import visitor_activity
from core.admin import DemoVisitorAdmin
from core.models import DemoVisitor
from core.roles import GROUP_VIEWER

OK = {"first_name": "Jan", "last_name": "Kowalski", "company": "ACME", "gdpr": "1"}


@override_settings(DEMO_PUBLIC=True, DEMO_VISITOR_GATE=True, NTFY_URL="", NTFY_ENGAGED_VIEWS=10)
class VisitorActivityTests(TestCase):
    def setUp(self):
        demo = User.objects.create_user("demo")
        demo.groups.add(Group.objects.create(name=GROUP_VIEWER))

    def _enter(self):
        r = self.client.post(reverse("core:demo_enter"), OK)
        self.assertRedirects(r, reverse("core:home"), fetch_redirect_response=False)
        return DemoVisitor.objects.get()

    def test_cookie_carries_signed_visitor_id(self):
        v = self._enter()
        self.assertIn(f"v{v.pk}:", self.client.cookies["demo_visitor"].value)

    def test_three_pages_counted(self):
        v = self._enter()
        for path in ("/", "/demo/", "/demo/?x=1"):
            self.assertEqual(self.client.get(path).status_code, 200)
        v.refresh_from_db()
        self.assertEqual(v.page_views, 3)
        self.assertEqual(v.sections, {"start": 1, "demo": 2})
        self.assertIsNotNone(v.last_seen_at)
        self.assertEqual(v.top_sections(), ["demo", "start"])

    def test_static_health_api_404_and_post_not_counted(self):
        v = self._enter()
        self.client.get("/static/core/nie-ma.css")
        self.client.get("/health/")
        self.client.get("/api/render/claim/")
        self.client.get(reverse("core:job_status", args=[999999]))
        self.assertEqual(self.client.get("/nie-ma-takiej-strony/").status_code, 404)
        self.client.post(reverse("core:demo_enter"))     # POST + przekierowanie
        v.refresh_from_db()
        self.assertEqual((v.page_views, v.sections, v.last_seen_at), (0, {}, None))

    def test_without_cookie_not_counted(self):
        DemoVisitor.objects.create(first_name="Jan", last_name="Nowak", company="Firma")
        self.client.get("/demo/")
        self.assertEqual(DemoVisitor.objects.get().page_views, 0)

    def test_forged_and_old_cookie_not_counted(self):
        v = DemoVisitor.objects.create(first_name="Jan", last_name="Nowak", company="Firma")
        self.client.cookies["demo_visitor"] = f"v{v.pk}"                        # bez podpisu
        self.client.get("/demo/")
        self.client.cookies["demo_visitor"] = f"v{v.pk}:podrobiony-podpis"
        self.client.get("/demo/")
        resp = HttpResponse()
        resp.set_signed_cookie("demo_visitor", "1")                            # stary format: wpuszcza, nie liczy
        self.client.cookies["demo_visitor"] = resp.cookies["demo_visitor"].value
        self.assertNotContains(self.client.get("/demo/"), "przedstaw się")
        v.refresh_from_db()
        self.assertEqual(v.page_views, 0)

    @mock.patch("core.visitor_activity.visitor_notify.notify_engaged")
    def test_engaged_push_exactly_once(self, engaged):
        v = self._enter()
        with override_settings(NTFY_ENGAGED_VIEWS=3):
            for _ in range(5):
                self.client.get("/demo/")
        engaged.assert_called_once_with({"first_name": "Jan", "last_name": "Kowalski", "company": "ACME"}, 3)
        v.refresh_from_db()
        self.assertEqual(v.page_views, 5)

    @mock.patch("core.visitor_activity.visitor_notify.notify_engaged")
    def test_engaged_push_disabled_with_zero(self, engaged):
        self._enter()
        with override_settings(NTFY_ENGAGED_VIEWS=0):
            self.client.get("/demo/")
        engaged.assert_not_called()

    def test_error_while_counting_does_not_break_response(self):
        self._enter()
        with mock.patch("core.visitor_activity.record", side_effect=RuntimeError("baza")), \
                self.assertLogs("core.visitor_activity", "WARNING"):
            r = self.client.get("/demo/")
        self.assertEqual(r.status_code, 200)

    def test_sections_capped_at_20(self):
        v = self._enter()
        v.sections = {f"s{i}": 1 for i in range(20)}
        v.save()
        visitor_activity.record(v.pk, "nowa")
        visitor_activity.record(v.pk, "s0")
        v.refresh_from_db()
        self.assertEqual(len(v.sections), 20)
        self.assertNotIn("nowa", v.sections)
        self.assertEqual((v.sections["s0"], v.page_views), (2, 2))

    def test_admin_list_shows_columns(self):
        v = self._enter()
        self.client.get("/demo/")
        admin_user = User.objects.create_superuser("szef", password="x")
        self.client.force_login(admin_user)
        with override_settings(TWO_FACTOR_ADMIN=False):
            r = self.client.get(reverse("admin:core_demovisitor_changelist"))
        for col in ("Ekrany", "Czas", "Najczęściej", "ok. 0 min"):
            self.assertContains(r, col)
        v.refresh_from_db()
        self.assertEqual(DemoVisitorAdmin.najczesciej(None, v), "demo")
        self.assertEqual(DemoVisitorAdmin.czas(None, DemoVisitor(first_name="a")), "—")


@override_settings(NTFY_URL="https://ntfy.example.com/t", NTFY_TOKEN="", NTFY_WATCH_COMPANIES="")
class EngagedRequestTests(SimpleTestCase):
    V = {"first_name": "Jan", "last_name": "Kowalski", "company": "ACME"}

    def test_normal_priority(self):
        from core.visitor_notify import build_engaged_request
        req = build_engaged_request(self.V, 10)
        headers = dict(req.header_items())
        self.assertEqual((headers["Title"], headers["Tags"], headers["Priority"]),
                         ("Gosc oglada demo: twinema", "eyes", "default"))
        self.assertEqual(req.data.decode("utf-8"), "Jan Kowalski (ACME) obejrzał już 10 ekranów w twinema")

    @override_settings(NTFY_WATCH_COMPANIES="acme")
    def test_watched_company_urgent(self):
        from core.visitor_notify import build_engaged_request
        self.assertEqual(build_engaged_request(self.V, 10).get_header("Priority"), "urgent")


class SectionTests(SimpleTestCase):
    def test_section_of(self):
        f = visitor_activity.section_of
        self.assertEqual(f("/"), "start")
        self.assertEqual(f("/palety/123"), "palety")
        self.assertEqual(f("/Prezentacje/1/"), "prezentacje")
        self.assertEqual(f("/x" + "a" * 60), ("x" + "a" * 60)[:40])
        self.assertEqual(f("/halaż!/"), "hala")
        self.assertIsNone(f("/żółć/"))

    def test_countable(self):
        rf = RequestFactory()
        self.assertTrue(visitor_activity.countable(rf.get("/hala/"), HttpResponse()))
        self.assertFalse(visitor_activity.countable(rf.get("/hala/dane.json"), JsonResponse({})))
        self.assertFalse(visitor_activity.countable(rf.get("/api/x/"), HttpResponse()))
        self.assertFalse(visitor_activity.countable(rf.get("/hala/api/x/"), HttpResponse()))
        self.assertFalse(visitor_activity.countable(rf.get("/static/a.css"), HttpResponse()))
        self.assertFalse(visitor_activity.countable(rf.get("/health/"), HttpResponse()))
        self.assertFalse(visitor_activity.countable(rf.get("/hala/"), HttpResponse(status=404)))
        self.assertFalse(visitor_activity.countable(rf.post("/hala/"), HttpResponse()))
