"""Publiczne demo: seed_demo dokłada symulację i prezentację z linkiem, /demo/ i wejście gościa (DEMO_PUBLIC)."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.demo import SHOWCASE, SHOWCASE_DAY, demo_showcase, mark_demo
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
        from core.demo import exposure_reasons
        self.assertEqual(exposure_reasons(), [])                      # US-011: same dane demo — bez ostrzeżenia


class DemoPageTests(TestCase):
    def setUp(self):
        wm = WarehouseModel.objects.create(name="Hala", floor_width_m=30, floor_depth_m=20)
        self.sc = Showcase.objects.create(title=SHOWCASE, model=wm, share_token="tok-demo",
                                          share_expires=timezone.now() + timedelta(days=30))
        mark_demo(wm, self.sc)
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

    def test_showcase_with_demo_title_but_not_from_seed_is_not_advertised(self):
        """Przegląd SEC (6): /demo/ wybiera pokaz z rejestru seed_demo, nie po tytule."""
        real = WarehouseModel.objects.create(name="Hala firmy", floor_width_m=30, floor_depth_m=20)
        Showcase.objects.create(title=SHOWCASE, model=real, share_token="tok-firmy",
                                share_expires=timezone.now() + timedelta(days=30))
        self.assertEqual(demo_showcase(), self.sc)
        self.assertNotContains(self.client.get(reverse("core:demo")), "tok-firmy")

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


class DemoExposureTests(TestCase):
    """US-011 (SEC, R-02): ostrzeżenie, gdy demo publiczne działa na instancji z danymi spoza demo."""

    def setUp(self):
        self.admin = User.objects.create_user("adm", password="x")
        self.admin.groups.add(Group.objects.get_or_create(name=GROUP_ADMIN)[0])
        self.viewer = User.objects.create_user("zarzad", password="x")
        self.viewer.groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])

    def _real_import(self):
        from masterdata.models import ImportLog
        ImportLog.objects.create(kind="materials", name="materialy.xlsx")

    def _check(self):
        err = StringIO()
        call_command("demo_exposure_check", stderr=err)
        return err.getvalue()

    def test_only_demo_data_no_warning(self):
        from masterdata.models import ImportLog
        mark_demo(ImportLog.objects.create(kind="stock", name="Demo — stany (hala)"))
        with self.settings(DEMO_PUBLIC=True):
            self.assertEqual(self._check(), "")

    def test_registry_decides_not_names(self):
        """Przegląd SEC (1): plik nazwany „Demo — …” i hala z prawdziwego pliku lokalizacji to dane spoza demo."""
        from core.demo import exposure_reasons
        from equipment.models import Equipment
        from masterdata.models import ImportLog
        from scenario.models import Scenario
        ImportLog.objects.create(kind="stock", name="Demo — stany.xlsx")
        WarehouseModel.objects.create(name="Hala z pliku lokalizacji")
        Scenario.objects.create(name="Plan 2027")
        Equipment.objects.create(kind="reach", name="Mój reach", capacity_kg=1500, speed_loaded_kmh=10,
                                 speed_empty_kmh=11, created_by=self.admin)
        self.assertEqual(exposure_reasons(), ["importy danych spoza demo", "hale spoza demo",
                                              "scenariusze spoza demo", "własne modele sprzętu"])

    @override_settings(DEMO_PUBLIC=True)
    def test_guest_already_inside_is_logged_out_when_real_data_appears(self):
        """Przegląd SEC (1): sesja gościa trwa do 8 h — sprawdzenie przy każdym żądaniu, nie tylko przy wejściu."""
        User.objects.create_user("demo").groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])
        self.client.post(reverse("core:demo_enter"))
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)
        self._real_import()
        r = self.client.get(reverse("core:home"))
        self.assertContains(r, "Wejście gościa jest wyłączone", status_code=403)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.force_login(self.viewer)                          # zwykły Podgląd pracuje dalej
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)

    def test_warning_in_logs_and_admin_banner(self):
        self._real_import()
        with self.settings(DEMO_PUBLIC=True):
            self.assertIn("importy danych spoza demo", self._check())
            self.client.force_login(self.admin)
            self.assertContains(self.client.get(reverse("core:home")), "Demo publiczne jest włączone")
            self.client.force_login(self.viewer)                      # Podgląd (także gość) banera nie widzi
            self.assertNotContains(self.client.get(reverse("core:home")), "Demo publiczne jest włączone")

    def test_demo_off_no_warning(self):
        self._real_import()
        with self.settings(DEMO_PUBLIC=False):
            self.assertEqual(self._check(), "")
            self.client.force_login(self.admin)
            self.assertNotContains(self.client.get(reverse("core:home")), "Demo publiczne jest włączone")

    def test_guest_entry_blocked_on_instance_with_real_data(self):
        """R-02 (decyzja PO): przy danych spoza demo gość nie wchodzi — strona demo nie pokazuje przycisku."""
        User.objects.create_user("demo").groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])
        with self.settings(DEMO_PUBLIC=True):
            self.assertContains(self.client.get(reverse("core:demo")), "Wejdź do systemu")
            self._real_import()
            self.assertNotContains(self.client.get(reverse("core:demo")), "Wejdź do systemu")
            r = self.client.post(reverse("core:demo_enter"))
            self.assertContains(r, "Wejście gościa jest wyłączone", status_code=403)
            self.assertNotIn("_auth_user_id", self.client.session)
            self.assertIn("Wejście gościa jest wyłączone", self._check())
