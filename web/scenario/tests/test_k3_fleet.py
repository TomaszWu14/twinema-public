"""K3 flota mieszana: silnik FleetMix (czysty Python), koszty per grupa, formularz, symulacja i animacja."""
from unittest import TestCase as PlainTestCase

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER
from equipment.models import Equipment
from scenario.costs import compute
from scenario.models import Scenario, ScenarioFleet, ScenarioRun
from scenario.sim import run_day
from scenario.sim.engine import FleetMix, dest_of, fleet_groups
from scenario.tests.test_costs import RATES
from scenario.tests.test_sim import DAY, NORMS, ONE_DOCK, STAFF
from twin.models import WarehouseModel
from core.jobs import run_pending


def group(role, units=1, move=4.0, leg=2.0, name=None):
    return {"name": name or role, "kind": role, "role": role, "units": units, "min_per_move": move, "leg_min": leg,
            "battery_h": 100, "charge_h": 1}


class FleetMixTests(PlainTestCase):
    def test_vna_pallet_goes_in_two_legs_transport_then_vna(self):
        f = FleetMix([group("transport", leg=6), group("vna", leg=3)])
        start, end = f.move(0, "vna")
        self.assertEqual(start, 0)
        self.assertAlmostEqual(end, 9 / 60)                             # 6 min AGV + 3 min VNA, bez czekania
        (tr,), (vna,) = (g["fleet"].busy for g in f.groups)
        self.assertAlmostEqual(tr[1], vna[0])                           # VNA startuje, gdy AGV dowiezie paletę

    def test_rack_pallet_one_move_of_rack_group_or_substitute(self):
        f = FleetMix([group("transport", move=5), group("rack", move=4)])
        self.assertEqual(f.move(0, "rack"), (0, 4 / 60))
        only_tr = FleetMix([group("transport", move=5)])
        self.assertEqual(only_tr.move(0, "rack"), (0, 5 / 60))         # brak reach → transport w jednym ruchu
        self.assertEqual(only_tr.move(1, "vna"), (1, 1 + 5 / 60))      # brak VNA → też jednym ruchem

    def test_old_params_give_one_group_and_dest_split(self):
        g = fleet_groups(NORMS)
        self.assertEqual((len(g), g[0]["role"], g[0]["units"]), (1, "any", NORMS["fleet_units"]))
        self.assertEqual({dest_of(i, 0) for i in range(50)}, {"rack"})
        self.assertEqual({dest_of(i, 1) for i in range(50)}, {"vna"})
        share = sum(dest_of(f"p{i}", 0.3) == "vna" for i in range(2000)) / 2000
        self.assertAlmostEqual(share, 0.3, delta=0.04)

    def test_run_day_reports_per_group(self):
        p = {**NORMS, "fleet_groups": [group("transport", 3, leg=2), group("vna", 2, leg=3)], "vna_share": 0.5}
        kpi = run_day(DAY, p, STAFF, ONE_DOCK, 5)["kpi"]
        self.assertEqual([g["role"] for g in kpi["fleet_groups"]], ["transport", "vna"])
        self.assertTrue(all(g["busy_h"] > 0 for g in kpi["fleet_groups"]))


class MixedCostsTests(PlainTestCase):
    def test_fleet_list_splits_hours_by_share(self):
        fleets = [{"name": "AGV", "units": 3, "share": 0.75, "purchase": (100, 100), "hour": (10, 10)},
                  {"name": "VNA", "units": 1, "share": 0.25, "purchase": (500, 500), "hour": (20, 20)}]
        c = compute(RATES, {"positions": {}, "docks": 0, "stations": 0}, fleets, 0,
                    [{"kind": "typical", "days": 10, "fleet_busy_h": 8, "volumes": {}}])
        capex = {i["label"]: i["low"] for i in c["capex"]["items"]}
        opex = {i["label"]: (i["qty"], i["low"]) for i in c["opex"]["items"]}
        self.assertEqual((capex["Flota: AGV"], capex["Flota: VNA"]), (300, 500))
        self.assertEqual(opex["Flota: AGV (energia, serwis)"], (60, 600))     # 80 h × 0,75
        self.assertEqual(opex["Flota: VNA (energia, serwis)"], (20, 400))


class MixedFleetViewTests(TestCase):
    def setUp(self):
        u = User.objects.create_user("proj", password="x")
        u.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.client.force_login(u)
        self.client.post(reverse("scenario:create"), {"name": "Flota mieszana"})
        self.sc = Scenario.objects.get()
        self.wm = WarehouseModel.objects.create(name="Hala", floor_width_m=80, floor_depth_m=50)
        for i in range(4):
            self.wm.racks.create(zone="V", rack_id=f"{i:03d}", n_bays=10, n_levels=8, level_height_cm=150,
                                 x_m=20, y_m=5 + 4 * i, equipment="vna" if i < 2 else "reach")
        for i, label in enumerate(("Dok kontenerowy 1", "Dok paletowy", "Dok FTL", "Dok paczek")):
            self.wm.features.create(kind="dock", label=label, x_m=0, y_m=6 * i, width_m=3.5, depth_m=4)
        self.agv = Equipment.objects.filter(kind="agv").first()
        self.vna = Equipment.objects.filter(kind="vna").first()

    def save_fleet(self, rows):
        data = {"fleet-TOTAL_FORMS": len(rows), "fleet-INITIAL_FORMS": 0}
        for i, (eq, n) in enumerate(rows):
            data |= {f"fleet-{i}-equipment": eq.pk, f"fleet-{i}-units": n}
        return self.client.post(reverse("scenario:fleet_save", args=[self.sc.pk]), data)

    def test_save_simulate_show_cost_animate_copy(self):
        self.save_fleet([(self.agv, 3), (self.vna, 2)])
        self.assertEqual(list(self.sc.fleet.values_list("units", flat=True)), [3, 2])
        self.client.post(reverse("scenario:simulate", args=[self.sc.pk]),
                         {"model": self.wm.pk, "day": "typical", "runs": 2})
        run_pending()                                   # US-007: symulację liczy worker kolejki
        res = ScenarioRun.objects.get().result
        g = {x["role"]: x for x in res["fleet_groups"]}
        self.assertEqual(set(g), {"transport", "vna"})
        self.assertLess(g["transport"]["leg_min"], g["transport"]["min_per_move"])   # etap AGV: bez podnoszenia
        self.assertLess(g["vna"]["leg_min"], g["vna"]["min_per_move"])               # etap VNA: krótszy odcinek
        self.assertEqual(len(res["rep"]["kpi"]["fleet_groups"]), 2)

        page = self.client.get(reverse("scenario:detail", args=[self.sc.pk]))
        self.assertContains(page, "Flota mieszana — przebieg reprezentatywny")
        self.assertContains(page, f"Flota: {self.agv.name}")
        self.assertContains(page, f"Flota: {self.vna.name} (energia, serwis)")

        play = self.client.get(reverse("scenario:run_play", args=[ScenarioRun.objects.get().pk]))
        self.assertContains(play, '"fleet_kinds": {"vna": "vna", "transport": "agv"}')

        self.client.post(reverse("scenario:copy", args=[self.sc.pk]))
        self.assertEqual(ScenarioFleet.objects.count(), 4)

    def test_form_offers_vehicles_only_and_rejects_zero(self):
        page = self.client.get(reverse("scenario:detail", args=[self.sc.pk]))
        self.assertContains(page, "Zapisz flotę")
        sorter = Equipment.objects.filter(kind="sorter").first()
        self.save_fleet([(sorter, 1)])
        self.save_fleet([(self.agv, 0)])
        self.assertFalse(self.sc.fleet.exists())
