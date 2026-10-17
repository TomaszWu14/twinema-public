"""Prezentacje 3D (P1): walidacja slajdów, karty KPI, szablon startowy, widoki i role."""
import json
from unittest import TestCase as PureTestCase

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from scenario.models import Scenario, ScenarioRun, Showcase
from scenario.showcase import SlideError, clean_slides, kpi_cards, summary_caption, template_slides
from twin.models import WarehouseModel
from core.jobs import run_pending


class SlideTests(PureTestCase):
    def test_clean_slides_normalises_and_validates(self):
        out = clean_slides([
            {"type": "camera", "title": "  Hala  ogólnie ", "cam": {"pos": [1, 2, 3], "target": [0, 0, 0]}},
            {"type": "camera", "cam": {"preset": "zone:V"}},
            {"type": "kpi", "cards": ["capacity", "capacity", "site"]},
            {"type": "anim", "t0": 3600, "t1": 7200, "speed": 120},
            {"type": "bottleneck", "index": 2, "caption": "x"},
            {"type": "text", "title": "Wnioski"},
        ])
        self.assertEqual(out[0]["title"], "Hala ogólnie")
        self.assertEqual(out[0]["cam"], {"pos": [1.0, 2.0, 3.0], "target": [0.0, 0.0, 0.0]})
        self.assertEqual(out[2]["cards"], ["capacity", "site"])
        self.assertEqual(out[2]["cam"], {"preset": "iso"})                   # plansza KPI na tle izometrii
        self.assertEqual((out[3]["t0"], out[3]["t1"], out[3]["speed"]), (3600, 7200, 120))
        bad = [None, [{"type": "film"}], [{"type": "camera", "cam": {"preset": "dron"}}],
               [{"type": "camera", "cam": {"pos": [1, 2], "target": [0, 0, 0]}}],
               [{"type": "camera", "cam": {"pos": [float("nan"), 0, 0], "target": [0, 0, 0]}}],
               [{"type": "kpi", "cards": ["zysk"]}], [{"type": "anim", "t0": 10, "t1": 5, "speed": 60}],
               [{"type": "anim", "t0": 0, "t1": 5, "speed": 7}], [{"type": "bottleneck", "index": True}],
               [{"type": "text", "title": "x" * 121}], [{"type": "text"}] * 61]
        for b in bad:
            with self.subTest(b=str(b)[:60]), self.assertRaises(SlideError):
                clean_slides(b)

    def test_kpi_cards(self):
        groups = [("Przepustowość", [{"label": "Palet IN", "unit": "", "mean": "640", "worst": "590"}] * 8),
                  ("Doki", []), ("Obsada", [])]
        cards = kpi_cards(groups, {"positions": 1200, "need": 900, "fill_pct": 75.0},
                          {"plot_m2": 50000, "coverage_pct": 41.2, "bio_pct": 22.0, "reserve_m2": 8000,
                           "building_height_m": 17.0})
        self.assertEqual(set(cards), {"throughput", "docks", "staff", "capacity", "site"})
        self.assertEqual(len(cards["throughput"]["rows"]), 6)                 # karta czytelna: maks. 6 wierszy
        self.assertEqual(cards["capacity"]["rows"][0]["value"], "1 200")
        self.assertEqual(cards["site"]["rows"][1]["value"], "41,2")
        self.assertEqual(kpi_cards(), {})

    def test_costs_card(self):
        costs = {"capex": {"low": 1_200_000, "high": 1_850_000}, "opex": {"low": 640_600, "high": 910_000},
                 "per_unit": {"pallets": {"label": "paletę", "low": 3.2, "high": 4.55}}}
        rows = kpi_cards(costs=costs)["costs"]["rows"]
        self.assertEqual([(r["label"], r["value"].replace("\xa0", " "), r["unit"]) for r in rows], [
            ("CAPEX (layout i flota)", "1 200–1 850", "tys. zł"), ("OPEX roczny", "641–910", "tys. zł/rok"),
            ("OPEX na paletę", "3,20–4,55", "zł")])

    def test_summary_and_template_without_run(self):
        self.assertIn("Hala mieści 1 200 miejsc paletowych (wypełnienie 75,0 %).",
                      summary_caption({"positions": 1200, "need": 900, "fill_pct": 75.0}))
        self.assertIn("Hala mieści 1 200 miejsc paletowych.",           # bez stanu — bez „0,0 %”
                      summary_caption({"positions": 1200, "need": 0, "fill_pct": 0.0}))
        self.assertIn("W dniu szczytowym przyjmuje średnio 900 palet",
                      summary_caption({"day": "szczytowym", "pallets_in": 900, "pallets_out": 800, "parcels": 10}))
        s = template_slides(title="Projekt", floor={"width": 60, "depth": 40},
                            racks=[{"zone": "V", "n_levels": 6}, {"zone": "K", "n_levels": 4}, {"zone": "V", "n_levels": 6}],
                            places={"docks": {}})
        self.assertEqual([x["type"] for x in s], ["text", "camera", "camera", "camera", "text"])
        self.assertEqual(s[2]["cam"], {"preset": "zone:V"})                  # największa strefa najpierw


class ShowcaseViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.designer = User.objects.create_user("proj", password="x")
        cls.designer.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        cls.viewer = User.objects.create_user("zarzad", password="x")
        cls.viewer.groups.add(Group.objects.create(name=GROUP_VIEWER))

    def setUp(self):
        self.client.force_login(self.designer)
        self.client.post(reverse("scenario:create"), {"name": "Rok bazowy"})
        self.sc = Scenario.objects.get()
        self.wm = WarehouseModel.objects.create(name="Hala testowa", floor_width_m=80, floor_depth_m=50)
        for i, label in enumerate(("Dok kontenerowy 1", "Dok paletowy", "Dok FTL")):
            self.wm.features.create(kind="dock", label=label, x_m=0, y_m=5 * i, width_m=3.5, depth_m=4)
        self.wm.features.create(kind="staging", label="Bufor przyjęć", x_m=5, y_m=5, width_m=10, depth_m=20)
        self.wm.racks.create(zone="V", rack_id="001", n_bays=6, n_levels=4, x_m=30, y_m=10)
        self.client.post(reverse("scenario:simulate", args=[self.sc.pk]),
                         {"model": self.wm.pk, "day": "typical", "runs": 2})
        run_pending()                                   # US-007: symulację liczy worker kolejki
        self.run = ScenarioRun.objects.get()

    def _create(self, **extra):
        r = self.client.post(reverse("scenario:showcase_create"),
                             {"title": "Pokaz dla zarządu", "model": self.wm.pk, "run": self.run.pk, **extra})
        return r, Showcase.objects.first()

    def test_create_from_template_with_results(self):
        r, sc = self._create()
        self.assertRedirects(r, reverse("scenario:showcase", args=[sc.pk]))
        types = [s["type"] for s in sc.slides]
        self.assertEqual(types[0], "text")
        self.assertIn("kpi", types)
        self.assertIn("anim", types)
        self.assertIn({"preset": "docks"}, [s.get("cam") for s in sc.slides])
        summary = sc.slides[-1]
        self.assertEqual(summary["title"], "Podsumowanie")
        pallets_in = round(self.run.result["agg"]["pallets_in"]["mean"])
        self.assertIn(f"W dniu typowym przyjmuje średnio {pallets_in:,}".replace(",", " "), summary["caption"])
        kpi = next(s for s in sc.slides if s["type"] == "kpi")
        self.assertEqual(kpi["cards"][:3], ["throughput", "docks", "staff"])

    def test_run_must_match_model(self):
        other = WarehouseModel.objects.create(name="Inna", floor_width_m=10, floor_depth_m=10)
        self.client.post(reverse("scenario:showcase_create"), {"title": "X", "model": other.pk, "run": self.run.pk})
        self.assertFalse(Showcase.objects.exists())

    def test_viewer_plays_but_cannot_edit(self):
        _, sc = self._create()
        self.client.force_login(self.viewer)
        page = self.client.get(reverse("scenario:showcase", args=[sc.pk]))
        self.assertContains(page, 'id="sh-canvas"')
        self.assertContains(page, "showcase.js")
        self.assertContains(page, 'id="sh-fs"')
        self.assertContains(page, "Wersja tekstowa slajdów")
        self.assertNotContains(page, 'id="sh-list"')                         # bez edytora
        data = self.client.get(reverse("scenario:showcase_data", args=[sc.pk])).json()
        self.assertEqual(data["format"], "twinema.showcase")
        self.assertEqual(len(data["slides"]), len(sc.slides))
        self.assertTrue(data["has_events"] and data["places"]["docks"] and data["cards"])
        self.assertIn("costs", data["cards"])                                # P2: plansza kosztów z wyniku symulacji
        self.assertNotIn("materials", json.dumps(data))
        for url, body in ((reverse("scenario:showcase_save", args=[sc.pk]), {"content_type": "application/json"}),
                          (reverse("scenario:showcase_reset", args=[sc.pk]), {}),
                          (reverse("scenario:showcase_delete", args=[sc.pk]), {})):
            self.assertEqual(self.client.post(url, data="{}", **body).status_code if body else
                             self.client.post(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("scenario:showcase_create"),
                                          {"title": "X", "model": self.wm.pk}).status_code, 403)
        self.assertEqual(self.client.get(reverse("scenario:showcase_list")).status_code, 200)

    def test_save_validates_and_reorders(self):
        _, sc = self._create()
        url = reverse("scenario:showcase_save", args=[sc.pk])
        new = list(reversed(sc.slides))
        r = self.client.post(url, data=json.dumps({"slides": new}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        sc.refresh_from_db()
        self.assertEqual(sc.slides[0]["title"], "Podsumowanie")
        bad = self.client.post(url, data=json.dumps({"slides": [{"type": "film"}]}), content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("Slajd 1", bad.json()["error"])
        self.assertEqual(self.client.post(url, data="nie-json", content_type="application/json").status_code, 400)
        sc.refresh_from_db()
        self.assertEqual(sc.slides[0]["title"], "Podsumowanie")              # zły zapis nic nie zmienia

    def test_reset_delete_list_and_links(self):
        _, sc = self._create()
        Showcase.objects.filter(pk=sc.pk).update(slides=[])
        self.client.post(reverse("scenario:showcase_reset", args=[sc.pk]))
        sc.refresh_from_db()
        self.assertTrue(sc.slides)
        lst = self.client.get(reverse("scenario:showcase_list") + f"?run={self.run.pk}")
        self.assertContains(lst, "Pokaz dla zarządu")
        self.assertContains(lst, f'<option value="{self.run.pk}" selected>')
        self.assertEqual(self.client.get(reverse("scenario:showcase_list") + "?run=abc").status_code, 200)
        detail = self.client.get(reverse("scenario:detail", args=[self.sc.pk]))
        self.assertContains(detail, f"{reverse('scenario:showcase_list')}?run={self.run.pk}")
        self.assertContains(self.client.get(reverse("core:home")), reverse("scenario:showcase_list"))
        self.client.post(reverse("scenario:showcase_delete", args=[sc.pk]))
        self.assertFalse(Showcase.objects.exists())

    def test_model_without_run(self):
        self.client.post(reverse("scenario:showcase_create"), {"title": "Sam layout", "model": self.wm.pk})
        sc = Showcase.objects.get()
        self.assertNotIn("kpi", [s["type"] for s in sc.slides])
        self.assertNotIn("anim", [s["type"] for s in sc.slides])
        data = self.client.get(reverse("scenario:showcase_data", args=[sc.pk])).json()
        self.assertFalse(data["has_events"])

    def test_pinned_run_survives_run_limit(self):
        """US-025: limit przebiegów scenariusza nie usuwa wyniku przypiętego do prezentacji."""
        from scenario import services
        _, show = self._create()
        for _ in range(services.KEEP_RUNS + 2):
            ScenarioRun.objects.create(scenario=self.sc, day_kind="typical", model=self.wm, runs=1, seed=1,
                                       duration_s=0, events=[], result=self.run.result)
        services.prune_runs(self.sc)
        self.assertTrue(ScenarioRun.objects.filter(pk=self.run.pk).exists())
        self.assertEqual(ScenarioRun.objects.filter(scenario=self.sc).count(), services.KEEP_RUNS + 1)
        show.refresh_from_db()
        self.assertEqual(show.run_id, self.run.pk)

    def test_designer_warned_when_pinned_run_was_deleted(self):
        """US-025: usunięcie scenariusza zabiera wynik — prezentacja ostrzega Projektanta, nie Podgląd."""
        _, show = self._create()
        self.client.post(reverse("scenario:delete", args=[self.sc.pk]))
        show.refresh_from_db()
        self.assertIsNone(show.run_id)
        self.assertIsNotNone(show.run_removed_at)
        self.assertContains(self.client.get(reverse("scenario:showcase", args=[show.pk])),
                            "Wynik symulacji przypięty do tej prezentacji został usunięty")
        self.assertContains(self.client.get(reverse("scenario:showcase_list")), "wynik symulacji usunięty")
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(reverse("scenario:showcase", args=[show.pk])),
                               "Wynik symulacji przypięty")
