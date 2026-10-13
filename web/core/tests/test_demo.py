"""Publiczne demo: seed_demo dokłada symulację i prezentację z linkiem, /demo/ i wejście gościa (DEMO_PUBLIC)."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.demo import SHOWCASE, SHOWCASE_DAY, demo_showcase
from core.roles import GROUP_ADMIN, GROUP_VIEWER
from scenario.models import ScenarioRun, Showcase
from twin.models import WarehouseModel


@override_settings(DEMO_PASSWORD="", DEMO_PUBLIC=True)
class SeedDemoShowcaseTests(TestCase):
    def test_runs_showcase_and_stable_link_idempotent(self):
        call_command("seed_demo", stdout=StringIO())
        sc = Showcase.objects.get(title=SHOWCASE)
        self.assertEqual(sc.run.day_kind, SHOWCASE_DAY)
        self.assertTrue(sc.slides and sc.share_token)
        self.assertGreater(sc.share_expires, timezone.now() + timedelta(days=365))
        runs = ScenarioRun.objects.count()
        self.assertEqual(runs, 2)                                     # dzień typowy i szczytowy
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual((ScenarioRun.objects.count(), Showcase.objects.count()), (runs, 1))
        self.assertEqual(Showcase.objects.get().share_token, sc.share_token)   # link się nie zmienia
        demo = User.objects.get(username="demo")                      # DEMO_PUBLIC bez hasła: konto bez logowania hasłem
        self.assertFalse(demo.has_usable_password())
        self.assertEqual(self.client.get(reverse("scenario:public", args=[sc.share_token])).status_code, 200)


class DemoPageTests(TestCase):
    def setUp(self):
        wm = WarehouseModel.objects.create(name="Hala", floor_width_m=30, floor_depth_m=20)
        self.sc = Showcase.objects.create(title=SHOWCASE, model=wm, share_token="tok-demo",
                                          share_expires=timezone.now() + timedelta(days=30))
        self.viewer_group = Group.objects.create(name=GROUP_VIEWER)

    def _demo_user(self, **kw):
        user = User.objects.create_user("demo", **kw)
        user.groups.add(self.viewer_group)
        return user

    def test_demo_page_links_showcase_without_login(self):
        r = self.client.get(reverse("core:demo"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reverse("scenario:public", args=["tok-demo"]))
        self.assertEqual(r["Referrer-Policy"], "same-origin")
        self.assertNotContains(r, reverse("core:demo_enter"))         # bez DEMO_PUBLIC nie ma wejścia gościa

    def test_expired_link_hidden(self):
        Showcase.objects.update(share_expires=timezone.now() - timedelta(minutes=1))
        self.assertIsNone(demo_showcase())
        self.assertNotContains(self.client.get(reverse("core:demo")), "/p/")

    @override_settings(DEMO_VIDEO_URL="https://www.youtube.com/watch?v=abc")
    def test_video_button(self):
        self.assertContains(self.client.get(reverse("core:demo")), "https://www.youtube.com/watch?v=abc")

    def test_home_anonymous_goes_to_login_without_demo_public(self):
        self.assertRedirects(self.client.get("/"), "/login/?next=/", fetch_redirect_response=False)

    @override_settings(DEMO_PUBLIC=True)
    def test_home_anonymous_goes_to_demo_page(self):
        self.assertRedirects(self.client.get("/"), reverse("core:demo"))
        self.assertContains(self.client.get(reverse("core:login")), reverse("core:demo"))

    def test_enter_disabled_without_demo_public(self):
        self._demo_user()
        self.assertEqual(self.client.post(reverse("core:demo_enter")).status_code, 404)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(DEMO_PUBLIC=True)
    def test_enter_logs_in_viewer_read_only(self):
        demo = self._demo_user()
        self.assertEqual(self.client.get(reverse("core:demo_enter")).status_code, 405)   # tylko POST (CSRF)
        r = self.client.post(reverse("core:demo_enter"))
        self.assertRedirects(r, reverse("core:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), demo.pk)
        self.assertContains(self.client.get(reverse("core:home")), "Wersja demo — tylko podgląd")
        self.assertEqual(self.client.get(reverse("masterdata:materials")).status_code, 403)

    @override_settings(DEMO_PUBLIC=True)
    def test_enter_refuses_privileged_demo_account(self):
        demo = self._demo_user()
        demo.groups.add(Group.objects.create(name=GROUP_ADMIN))
        self.assertEqual(self.client.post(reverse("core:demo_enter")).status_code, 404)
        User.objects.filter(pk=demo.pk).update(is_superuser=True)
        demo.groups.remove(Group.objects.get(name=GROUP_ADMIN))
        self.assertEqual(self.client.post(reverse("core:demo_enter")).status_code, 404)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(DEMO_PUBLIC=True)
    def test_enter_keeps_existing_session(self):
        other = User.objects.create_user("proj", password="x")
        self._demo_user()
        self.client.force_login(other)
        self.client.post(reverse("core:demo_enter"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), other.pk)
