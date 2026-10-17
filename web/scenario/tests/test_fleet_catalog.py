"""Flota scenariusza z katalogu sprzętu (K1): czas ruchu palety z parametrów, bateria i ładowanie w symulacji."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER
from equipment.catalog import move_minutes
from equipment.models import Equipment
from scenario.models import Scenario, ScenarioRun
from scenario.services import fleet_from_catalog
from scenario.sim.engine import Fleet
from twin.models import WarehouseModel
from core.jobs import run_pending


class FleetChargingTests(TestCase):
    def test_battery_sends_unit_to_charging(self):
        f = Fleet(1, battery_h=2, charge_h=1)
        f.take(0, 1.5)
        start, _ = f.take(0, 1)                     # 2,5 h pracy ≥ 2 h baterii → ładowanie po tym zadaniu
        self.assertEqual(start, 1.5)
        self.assertEqual(f.charging, [(2.5, 3.5)])
        self.assertEqual(f.take(0, 0.5)[0], 3.5)    # następne zadanie dopiero po ładowaniu


class FleetCatalogTests(TestCase):
    def setUp(self):
        u = User.objects.create_user("proj", password="x")
        u.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.client.force_login(u)
        self.client.post(reverse("scenario:create"), {"name": "Rok bazowy"})
        self.sc = Scenario.objects.get()
        self.wm = WarehouseModel.objects.create(name="Hala", floor_width_m=80, floor_depth_m=50)
        for i in range(4):
            self.wm.racks.create(zone="V", rack_id=f"{i:03d}", n_bays=10, n_levels=5, level_height_cm=200,
                                 x_m=20, y_m=5 + 4 * i)
        for i, label in enumerate(("Dok kontenerowy 1", "Dok paletowy", "Dok FTL", "Dok paczek")):
            self.wm.features.create(kind="dock", label=label, x_m=0, y_m=6 * i, width_m=3.5, depth_m=4)
        self.reach = Equipment.objects.get(name="Reach truck 1,6 t / 10 m")

    def test_move_time_from_layout_distance_and_lift(self):
        f = fleet_from_catalog(self.reach, self.wm)
        self.assertEqual(f["lift_m"], 4.0)                              # średnia belka: (5-1)/2 × 2,0 m
        self.assertGreater(f["dist_m"], 10)
        self.assertAlmostEqual(f["min_per_move"], round(move_minutes(self.reach.params(), f["dist_m"], 4.0), 2))
        self.assertEqual((f["battery_h"], f["charge_h"]), (6, 2))

    def test_simulation_uses_catalog_fleet_and_reports_effective_fleet(self):
        Scenario.objects.filter(pk=self.sc.pk).update(fleet_equipment=self.reach, fleet_units=4)
        self.client.post(reverse("scenario:simulate", args=[self.sc.pk]),
                         {"model": self.wm.pk, "day": "typical", "runs": 2})
        run_pending()                                   # US-007: symulację liczy worker kolejki
        res = ScenarioRun.objects.get().result
        self.assertEqual(res["fleet"]["name"], "Reach truck 1,6 t / 10 m")
        agg = res["agg"]
        self.assertGreater(agg["fleet_charge_h"]["mean"], 0)           # 6 h na baterii → ładowania w ciągu doby
        self.assertLess(agg["fleet_effective"]["mean"], 4)
        page = self.client.get(reverse("scenario:detail", args=[self.sc.pk]))
        self.assertContains(page, "Flota z katalogu")
        self.assertContains(page, "Flota efektywna")

    def test_scenario_form_offers_vehicles_only(self):
        page = self.client.get(reverse("scenario:detail", args=[self.sc.pk]))
        self.assertContains(page, "VNA kombi 1,5 t / 14 m")
        self.assertNotContains(page, "Sorter paczek")
