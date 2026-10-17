"""Testy end-to-end w przeglądarce (Playwright, Chromium) — kluczowe ścieżki i CSP (STRATEGIA_TESTOW, US-005).

Uruchamiane tagiem `e2e` (osobny job CI): `python manage.py test --tag e2e`. Bez zainstalowanego Playwrighta
test jest pomijany. Dane: `seed_demo` (hala, scenariusz, prezentacja z linkiem publicznym, konto demo).
Każda strona zbiera błędy JavaScript i naruszenia polityki CSP — wynik ma być pusty.
"""

import os
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.test import override_settings, tag
from django.urls import reverse

from core.roles import GROUP_DESIGNER

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                       # pragma: no cover — środowisko bez Playwrighta
    sync_playwright = None

# Playwright uruchamia pętlę asyncio w wątku testu; ORM w tym wątku jest bezpieczny (testy są sekwencyjne).
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

# Zbiera naruszenia CSP i błędy JS w każdej stronie (także po nawigacji) — czyta je `_problems`.
WATCH = """
window.__problems = [];
document.addEventListener('securitypolicyviolation', e =>
  window.__problems.push('CSP ' + e.violatedDirective + ' ' + (e.blockedURI || 'inline') + ' @' + e.lineNumber));
window.addEventListener('error', e => window.__problems.push('JS ' + e.message));
"""


def _chromium_path():
    """Chromium z obrazu środowiska (PLAYWRIGHT_BROWSERS_PATH) albo pobrany przez `playwright install`."""
    custom = os.environ.get("E2E_CHROMIUM")
    return custom if custom and Path(custom).exists() else None


@tag("e2e")
@override_settings(DEMO_PUBLIC=True, DEMO_PASSWORD="", DEBUG=False)
class KeyPathsE2ETests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        if sync_playwright is None:
            raise __import__("unittest").SkipTest("Playwright nie jest zainstalowany")
        super().setUpClass()
        cls._pw = sync_playwright().start()
        cls.browser = cls._pw.chromium.launch(executable_path=_chromium_path())

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._pw.stop()
        super().tearDownClass()

    def _fresh_browser(self):
        if getattr(self, "context", None):
            self.context.close()
        self.context = self.browser.new_context(locale="pl-PL")
        self.context.add_init_script(WATCH)
        self.page = self.context.new_page()
        self.console_errors = []
        self.page.on("console", lambda m: m.type == "error" and self.console_errors.append(m.text))

    def tearDown(self):
        if getattr(self, "context", None):
            self.context.close()

    def test_key_paths(self):
        """Jeden test: baza testu na żywym serwerze jest czyszczona po teście razem z danymi z migracji
        (stawki, klasy sprzętu), więc ścieżki dzielą jedno wypełnienie danymi demo."""
        call_command("seed_demo", verbosity=0, stdout=open(os.devnull, "w"))
        self.designer = User.objects.create_user("projektant", password="Haslo-testowe-123")
        self.designer.groups.add(Group.objects.get(name=GROUP_DESIGNER))
        for flow in (self._designer_logs_in_and_walks_main_screens, self._scenario_page_shows_simulation_result,
                     self._pages_with_scripts_run_under_enforced_csp, self._guest_enters_demo_and_watches_public_showcase):
            with self.subTest(flow.__name__):
                self._fresh_browser()
                flow()

    def _open(self, path):
        response = self.page.goto(self.live_server_url + path)
        self.page.wait_for_load_state("networkidle")
        return response

    def _problems(self):
        return self.page.evaluate("window.__problems") + self.console_errors

    def _login(self):
        self._open("/login/")
        self.page.fill('input[name="username"]', "projektant")
        self.page.fill('input[name="password"]', "Haslo-testowe-123")
        self.page.click('button[type="submit"]')
        self.page.wait_for_url(self.live_server_url + "/")

    def _designer_logs_in_and_walks_main_screens(self):
        self._login()
        self.assertTrue(self.page.get_by_role("heading", name="Scenariusze").is_visible())
        seen = {}
        for name in ("core:home", "scenario:list", "equipment:list", "masterdata:home", "scenario:showcase_list",
                     "twin:warehouse_model_list", "twin:design_hub"):
            path = reverse(name)
            self.console_errors.clear()
            self.assertEqual(self._open(path).status, 200, path)
            seen[path] = self._problems()
        self.assertEqual({p: v for p, v in seen.items() if v}, {})

    def _scenario_page_shows_simulation_result(self):
        from scenario.models import Scenario
        self._login()
        sc = Scenario.objects.get()
        self._open(reverse("scenario:detail", args=[sc.pk]))
        self.assertTrue(self.page.locator("#sc-sim-h").is_visible())
        self.assertTrue(self.page.get_by_text("Wąskie gardła").first.is_visible())
        self.assertEqual(self._problems(), [])

    def _pages_with_scripts_run_under_enforced_csp(self):
        """US-005, R-20: ekrany ze skryptami (3D, edytory, wykresy) działają pod wymuszoną CSP — bez naruszeń i błędów JS;
        style= są zablokowane, więc kolory i szerokości z danych ustawia ui.js (data-color, data-pct)."""
        from equipment.models import Equipment
        from scenario.models import Scenario, ScenarioRun, Showcase
        from studio.models import Presentation
        from twin.models import WarehouseModel
        self._login()
        wm, sc, run, show = (WarehouseModel.objects.get(), Scenario.objects.get(), ScenarioRun.objects.first(),
                             Showcase.objects.get())
        film = Presentation.objects.create(title="Film demo", model=wm)
        pages = [reverse("scenario:detail", args=[sc.pk]), reverse("scenario:showcase", args=[show.pk]),
                 reverse("scenario:run_play", args=[run.pk]), reverse("scenario:compare"),
                 reverse("twin:warehouse_model_view", args=[wm.pk]), reverse("twin:warehouse_layout_editor", args=[wm.pk]),
                 reverse("twin:warehouse_model_features", args=[wm.pk]), reverse("twin:warehouse_model_coords", args=[wm.pk]),
                 reverse("twin:warehouse_rack_type_new"), reverse("render:jobs"), reverse("studio:detail", args=[film.pk]),
                 reverse("ml:home"), reverse("twin:warehouse_rack_type_list"),
                 reverse("equipment:detail", args=[Equipment.objects.order_by("pk").first().pk])]
        problems = {}
        for path in pages:
            self.console_errors.clear()
            response = self._open(path)
            self.assertEqual(response.status, 200, path)
            self.assertIn("'nonce-", response.headers.get("content-security-policy", ""), path)   # wymuszona, nie raport
            if found := self._problems():
                problems[path] = found
        self.assertEqual(problems, {})

        # zakładka planu 2D (atrybut hidden zamiast style="display:none") i kolor strefy z data-color
        self._open(reverse("twin:warehouse_model_view", args=[wm.pk]))
        self.page.click('.viz-tab[data-tab="2d"]')
        self.assertTrue(self.page.is_visible("#panel-2d"))
        self.assertFalse(self.page.is_visible("#panel-3d"))
        dot = self.page.locator(".zone-dot").first.evaluate("e => getComputedStyle(e).backgroundColor")
        self.assertNotIn(dot, ("", "rgba(0, 0, 0, 0)"))
        self.assertEqual(self._problems(), [])

    def _guest_enters_demo_and_watches_public_showcase(self):
        self._open("/")
        self.assertTrue(self.page.url.endswith("/demo/"))
        self.page.click("text=Obejrzyj prezentację 3D")
        self.page.wait_for_load_state("networkidle")
        self.assertIn("/p/", self.page.url)
        self.assertTrue(self.page.locator("canvas").first.is_visible())
        self.assertEqual(self._problems(), [])
        self._open("/demo/")
        self.page.click("text=Wejdź do systemu")
        self.page.wait_for_url(self.live_server_url + "/")
        self.assertFalse(self.page.get_by_role("link", name="Zadania EWM").count())
        self.assertEqual(self._problems(), [])
