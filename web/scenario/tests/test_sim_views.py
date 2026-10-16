"""Symulacja dnia w aplikacji (S3a): uruchomienie, wynik na ekranie scenariusza, role, zdarzenia JSON, demo."""
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from scenario.models import Scenario, ScenarioRun
from twin.models import WarehouseModel
from core.jobs import run_pending


class SimViewTests(TestCase):
    def setUp(self):
        self.designer = User.objects.create_user("proj", password="x")
        self.designer.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.viewer = User.objects.create_user("zarzad", password="x")
        self.viewer.groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.client.force_login(self.designer)
        self.client.post(reverse("scenario:create"), {"name": "Rok bazowy"})
        self.sc = Scenario.objects.get()
        self.wm = WarehouseModel.objects.create(name="Hala testowa", floor_width_m=80, floor_depth_m=50)
        for i, label in enumerate(("Dok kontenerowy 1", "Dok paletowy", "Dok FTL", "Dok FTL", "Dok paczek")):
            self.wm.features.create(kind="dock", label=label, x_m=0, y_m=5 * i, width_m=3.5, depth_m=4)
        self.wm.features.create(kind="staging", label="Bufor przyjęć", x_m=5, y_m=5, width_m=10, depth_m=20)

    def _run(self, **over):
        data = {"model": self.wm.pk, "day": "typical", "runs": 3, **over}
        r = self.client.post(reverse("scenario:simulate", args=[self.sc.pk]), data)
        if r.status_code != 302:
            return r
        run_pending()                                   # US-007: symulację liczy worker kolejki
        return self.client.get(r["Location"])

    def test_designer_runs_simulation_and_sees_result(self):
        r = self._run()
        run = ScenarioRun.objects.get()
        self.assertEqual((run.day_kind, run.model, run.runs, run.created_by), ("typical", self.wm, 3, self.designer))
        self.assertTrue(run.events)
        self.assertIn("pallets_in", run.result["agg"])
        self.assertContains(r, "Symulacja na „Hala testowa”")
        self.assertContains(r, "Wąskie gardła")
        self.assertContains(r, "Doki i pole odkładcze")
        self.assertContains(r, 'id="sc-sim-data"')
        self.assertContains(r, "Pole przyjęć: potrzeba / narysowane")

    def test_both_days(self):
        self._run(day="both")
        self.assertEqual(sorted(ScenarioRun.objects.values_list("day_kind", flat=True)), ["peak", "typical"])

    def test_same_seed_same_result(self):
        self._run()
        self._run()
        a, b = ScenarioRun.objects.order_by("pk")
        self.assertEqual(a.result["agg"], b.result["agg"])

    def test_viewer_sees_result_but_cannot_run(self):
        self._run()
        self.client.force_login(self.viewer)
        self.assertEqual(self._run().status_code, 403)
        page = self.client.get(reverse("scenario:detail", args=[self.sc.pk]))
        self.assertContains(page, "Wąskie gardła")
        self.assertNotContains(page, "Uruchom symulację")
        run = ScenarioRun.objects.get()
        ev = self.client.get(reverse("scenario:run_events", args=[run.pk])).json()
        self.assertEqual(ev["format"], "twinema.scenario-events")
        self.assertEqual(ev["columns"], ["t_s", "obj", "kind", "what", "place"])
        self.assertEqual(len(ev["events"]), len(run.events))

    def test_invalid_form_message(self):
        r = self._run(runs=99)
        self.assertContains(r, "liczbę przebiegów")
        self.assertFalse(ScenarioRun.objects.exists())

    def test_hall_without_docks_still_simulates_with_warning(self):
        bare = WarehouseModel.objects.create(name="Pusta hala", floor_width_m=40, floor_depth_m=30)
        r = self._run(model=bare.pk)
        self.assertContains(r, "dok zastępczy")

    def test_fleet_params_saved_with_scenario(self):
        data = {f: getattr(self.sc, f) for f in ("name", "description", "growth", "seed", "shift_h", "work_days",
                                                 *Scenario.NORM_FIELDS, "return_restock_pct")}
        data.update(fleet_units=20, fleet_min_per_move=3, battery_h=8, charge_h=1)
        self.client.post(reverse("scenario:save", args=[self.sc.pk]), data)
        self.sc.refresh_from_db()
        self.assertEqual((self.sc.fleet_units, self.sc.sim_params()["fleet_min_per_move"]), (20, 3))


class DemoSimTests(TestCase):
    def test_demo_typical_quiet_peak_has_bottlenecks(self):
        from scenario.services import simulate

        call_command("demo_scenariusz", stdout=StringIO())
        sc, wm = Scenario.objects.get(), WarehouseModel.objects.get(name__startswith="Hala demo")
        days = {d.kind: d for d in sc.days.prefetch_related("inbound", "outbound")}
        typical, peak = simulate(days["typical"], wm, runs=6), simulate(days["peak"], wm, runs=6)
        crit = [b for b in typical.result["bottlenecks"] if b["severity"] == "error"]
        self.assertEqual(crit, [])                                       # dzień typowy: najwyżej ostrzeżenia
        self.assertEqual(typical.result["agg"]["unfinished"]["worst"], 0)
        self.assertTrue(any(b["severity"] == "error" for b in peak.result["bottlenecks"]))
