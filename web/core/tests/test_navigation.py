"""R4: nawigacja w nagłówku z core.views.MODULES (te same nazwy co kafle), aktywna pozycja z aria-current,
wersja w /health/ z config.py."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import resolve, reverse

from core.views import MODULES, active_module


class NavigationTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("a", "a@x.pl", "x"))

    def test_nav_and_tiles_use_same_names(self):
        r = self.client.get("/")
        nav = r.context["nav_modules"]
        self.assertEqual([m["name"] for m in nav], [m["name"] for m in MODULES])
        self.assertEqual([m["name"] for m in r.context["modules"]], [m["name"] for m in MODULES])

    def test_active_module_by_url_name_then_app(self):
        cases = {"scenario:showcase_list": "prezentacje", "scenario:list": "scenariusze",
                 "twin:ewm_tasks_list": "zadania", "twin:design_hub": "projektowanie",
                 "twin:warehouse_model_list": "model", "equipment:list": "sprzet", "core:home": None}
        for name, key in cases.items():
            self.assertEqual(active_module(resolve(reverse(name))), key, name)

    def test_aria_current_on_active_only(self):
        html = self.client.get(reverse("scenario:showcase_list")).content.decode()
        self.assertEqual(html.count('aria-current="page"'), 1)
        self.assertIn(f'href="{reverse("scenario:showcase_list")}" class="is-active" aria-current="page"', html)

    @override_settings(GIT_SHA="abc123")
    def test_health_version_from_config(self):
        self.assertEqual(self.client.get("/health/").json()["version"], "abc123")


class SafeXlsxTests(TestCase):
    def test_openpyxl_uses_defusedxml(self):
        # R4: importy XLSX z plików użytkownika — openpyxl musi parsować przez defusedxml (requirements.txt)
        from openpyxl import xml
        self.assertTrue(xml.DEFUSEDXML)


class ViewerSeesOnlyAccessibleLinksTests(TestCase):
    """US-019: rola Podgląd nie widzi menu i przycisków prowadzących do stron bez dostępu (403)."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from core.roles import GROUP_DESIGNER, GROUP_VIEWER
        from twin.models import WarehouseModel
        self.viewer = User.objects.create_user("zarzad", password="x")
        self.viewer.groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])
        self.designer = User.objects.create_user("proj", password="x")
        self.designer.groups.add(Group.objects.get_or_create(name=GROUP_DESIGNER)[0])
        self.wm = WarehouseModel.objects.create(name="Hala nawigacji", floor_width_m=40, floor_depth_m=30)

    def _get(self, user, name, *args):
        self.client.force_login(user)
        return self.client.get(reverse(name, args=args))

    def test_viewer_menu_and_tiles_without_designer_modules(self):
        r = self._get(self.viewer, "core:home")
        tasks = reverse("twin:ewm_tasks_list")
        self.assertNotIn(tasks, [m["url"] for m in r.context["nav_modules"]])
        self.assertNotContains(r, f'href="{tasks}"')
        self.assertEqual(self._get(self.viewer, "twin:ewm_tasks_list").status_code, 403)   # nadal chronione
        self.assertContains(self._get(self.designer, "core:home"), f'href="{tasks}"')

    def test_hall_view_hides_editing_buttons_for_viewer(self):
        links = [reverse(n, args=[self.wm.pk]) for n in ("twin:warehouse_model_paste", "twin:warehouse_model_features",
                                                         "twin:warehouse_model_coords")]
        page = self._get(self.viewer, "twin:warehouse_model_view", self.wm.pk)
        for link in links:
            self.assertNotContains(page, f'href="{link}"')
        page = self._get(self.designer, "twin:warehouse_model_view", self.wm.pk)
        for link in links:
            self.assertContains(page, f'href="{link}"')

    def test_rack_types_and_design_hub_without_forbidden_links(self):
        self.assertNotContains(self._get(self.viewer, "twin:warehouse_rack_type_list"),
                               reverse("twin:warehouse_rack_type_new"))
        hub = self._get(self.viewer, "twin:design_hub")
        self.assertNotContains(hub, f'href="{reverse("twin:ewm_tasks_list")}"')
        self.assertNotContains(hub, f'href="{reverse("twin:warehouse_model_generator")}"')
        self.assertContains(hub, "Krok dla roli Projektant")
        self.assertContains(self._get(self.designer, "twin:design_hub"), f'href="{reverse("twin:ewm_tasks_list")}"')
