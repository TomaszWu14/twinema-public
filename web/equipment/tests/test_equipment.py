"""Katalog sprzętu (K1): czyste funkcje, klasy systemowe z migracji, dobór klasy do regałów, ekrany i role."""
from unittest import TestCase as PlainTestCase

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.roles import GROUP_ADMIN, GROUP_DESIGNER, GROUP_VIEWER
from equipment.catalog import capacity_at, move_minutes
from equipment.models import Equipment
from equipment.services import assign_classes, pick_class


class CatalogMathTests(PlainTestCase):
    def test_capacity_curve_interpolation(self):
        curve = [[6, 1600], [8, 1400], [10, 1000]]
        self.assertEqual(capacity_at(1600, curve, 0), 1600)          # poniżej pierwszego punktu — nominalny
        self.assertEqual(capacity_at(1600, curve, 7), 1500)          # liniowo między punktami
        self.assertEqual(capacity_at(1600, curve, 9), 1200)
        self.assertEqual(capacity_at(1600, curve, 12), 1000)         # ponad krzywą — ostatnia wartość
        self.assertEqual(capacity_at(2000, [], 15), 2000)            # brak krzywej = udźwig stały

    def test_move_minutes_from_parameters(self):
        eq = {"speed_loaded_kmh": 3.6, "speed_empty_kmh": 7.2, "lift_speed_ms": 0.5, "lower_speed_ms": 1.0,
              "pick_s": 10, "drop_s": 20}
        # 36 m z ładunkiem (36 s) + 36 m pusto (18 s) + 5 m w górę (10 s) i w dół (5 s) + 30 s obsługi = 99 s
        self.assertAlmostEqual(move_minutes(eq, 36, 5), 99 / 60)
        self.assertGreater(move_minutes(eq, 80, 5), move_minutes(eq, 20, 5))


class SystemClassesTests(TestCase):
    def test_migration_seeds_anonymous_classes(self):
        sys = Equipment.objects.filter(is_system=True)
        self.assertEqual(set(sys.values_list("kind", flat=True)),
                         {"pallet_truck", "counterbalance", "reach", "vna", "agv", "amr", "conveyor", "sorter",
                          "stacker", "order_picker", "tractor"})                        # + K2 klasy rynkowe
        reach = sys.get(name="Reach truck 1,6 t / 10 m")
        self.assertEqual((reach.max_lift_m, reach.aisle_m, reach.capacity_kg), (10, 2.9, 1600))
        self.assertEqual(reach.rack_category, "reach")

    def test_pick_class_covers_top_beam(self):
        self.assertEqual(pick_class("reach", 9).name, "Reach truck 1,6 t / 10 m")
        self.assertEqual(pick_class("reach", 11).name, "Reach truck 2,0 t / 12 m")
        self.assertEqual(pick_class("vna", 15).name, "VNA kombi 1,2 t / 17 m")
        self.assertEqual(pick_class("reach", 13).name, "Reach truck 2,5 t / 14 m")
        self.assertEqual(pick_class("vna", 30).name, "VNA kombi 1,6 t / 18 m")   # żadna nie sięga → najwyższa
        self.assertIsNone(pick_class("shelf", 1))
        racks = assign_classes([{"equipment": "vna", "n_levels": 5, "level_height_cm": 260},
                                {"equipment": "shelf", "n_levels": 5, "level_height_cm": 45}])
        self.assertEqual(racks[0]["equipment_model"].name, "VNA kombi 1,5 t / 14 m")
        self.assertIsNone(racks[1]["equipment_model"])


class CatalogViewTests(TestCase):
    def setUp(self):
        self.users = {}
        for name, group in (("adm", GROUP_ADMIN), ("proj", GROUP_DESIGNER), ("zarzad", GROUP_VIEWER)):
            u = User.objects.create_user(name, password="x")
            u.groups.add(Group.objects.get_or_create(name=group)[0])
            self.users[name] = u
        self.reach = Equipment.objects.get(name="Reach truck 1,6 t / 10 m")

    def test_list_filter_and_detail_curve(self):
        self.client.force_login(self.users["zarzad"])
        r = self.client.get(reverse("equipment:list") + "?typ=vna")
        self.assertContains(r, "VNA kombi 1,5 t / 14 m")
        self.assertNotContains(r, "Reach truck 1,6 t")
        d = self.client.get(reverse("equipment:detail", args=[self.reach.pk]))
        self.assertContains(d, "Udźwig na wysokości")
        self.assertContains(d, "1000 kg")
        self.assertNotContains(d, "Kopiuj jako własny model")              # Podgląd: tylko odczyt
        self.assertEqual(self.client.post(reverse("equipment:copy", args=[self.reach.pk])).status_code, 403)

    def test_designer_copies_class_but_cannot_edit_system(self):
        self.client.force_login(self.users["proj"])
        self.assertEqual(self.client.get(reverse("equipment:edit", args=[self.reach.pk])).status_code, 403)
        self.client.post(reverse("equipment:copy", args=[self.reach.pk]))
        own = Equipment.objects.get(is_system=False)
        self.assertEqual((own.name, own.max_lift_m, own.created_by), ("Reach truck 1,6 t / 10 m (kopia)", 10,
                                                                     self.users["proj"]))
        data = {f: getattr(own, f) for f in ("kind", "speed_loaded_kmh", "speed_empty_kmh", "lift_speed_ms",
                                             "lower_speed_ms", "max_lift_m", "capacity_kg", "aisle_m", "pick_s",
                                             "drop_s", "battery_h", "charge_h")}
        r = self.client.post(reverse("equipment:edit", args=[own.pk]),
                             {**data, "name": "Mój reach 11 m", "lift_curve": "[[11, 900], [6, 1600]]"})
        self.assertEqual(r.status_code, 302)
        own.refresh_from_db()
        self.assertEqual((own.name, own.lift_curve), ("Mój reach 11 m", [[6, 1600], [11, 900]]))
        bad = self.client.post(reverse("equipment:edit", args=[own.pk]), {**data, "name": "x", "lift_curve": "[[1]]"})
        self.assertContains(bad, "Lista punktów")
        self.client.post(reverse("equipment:delete", args=[own.pk]))
        self.assertFalse(Equipment.objects.filter(is_system=False).exists())
        self.assertEqual(self.client.post(reverse("equipment:delete", args=[self.reach.pk])).status_code, 403)

    def test_admin_edits_system_class(self):
        self.client.force_login(self.users["adm"])
        self.assertEqual(self.client.get(reverse("equipment:edit", args=[self.reach.pk])).status_code, 200)

    def test_hub_links_catalog(self):
        self.client.force_login(self.users["zarzad"])
        self.assertContains(self.client.get(reverse("core:home")), reverse("equipment:list"))


class OwnModelAuthorizationTests(TestCase):
    """US-001 (SEC): własny model sprzętu zmienia i usuwa tylko jego autor albo administrator."""

    def setUp(self):
        self.users = {}
        for name, group in (("adm", GROUP_ADMIN), ("autor", GROUP_DESIGNER), ("inny", GROUP_DESIGNER),
                            ("zarzad", GROUP_VIEWER)):
            u = User.objects.create_user(name, password="x")
            u.groups.add(Group.objects.get_or_create(name=group)[0])
            self.users[name] = u
        self.own = Equipment.objects.create(kind="reach", name="Mój reach", capacity_kg=1500, speed_loaded_kmh=10,
                                            speed_empty_kmh=11, created_by=self.users["autor"])
        self.orphan = Equipment.objects.create(kind="reach", name="Bez autora", capacity_kg=1500,
                                               speed_loaded_kmh=10, speed_empty_kmh=11)

    def _status(self, who, route, eq, method="get"):
        self.client.force_login(self.users[who])
        return getattr(self.client, method)(reverse(route, args=[eq.pk])).status_code

    def test_other_designer_and_viewer_get_403(self):
        for who in ("inny", "zarzad"):
            self.assertEqual(self._status(who, "equipment:edit", self.own), 403, who)
            self.assertEqual(self._status(who, "equipment:delete", self.own, "post"), 403, who)
        self.assertTrue(Equipment.objects.filter(pk=self.own.pk).exists())

    def test_model_without_author_only_admin(self):
        self.assertEqual(self._status("autor", "equipment:edit", self.orphan), 403)
        self.assertEqual(self._status("autor", "equipment:delete", self.orphan, "post"), 403)
        self.assertEqual(self._status("adm", "equipment:edit", self.orphan), 200)

    def test_detail_hides_actions_for_other_designer(self):
        self.client.force_login(self.users["inny"])
        page = self.client.get(reverse("equipment:detail", args=[self.own.pk]))
        self.assertNotContains(page, reverse("equipment:edit", args=[self.own.pk]))
        self.assertNotContains(page, reverse("equipment:delete", args=[self.own.pk]))
        self.assertContains(page, "Kopiuj jako własny model")             # kopia nadal dozwolona

    def test_author_and_admin_can_delete(self):
        self.assertEqual(self._status("autor", "equipment:edit", self.own), 200)
        self.assertEqual(self._status("autor", "equipment:delete", self.own, "post"), 302)
        self.assertEqual(self._status("adm", "equipment:delete", self.orphan, "post"), 302)
        self.assertFalse(Equipment.objects.filter(is_system=False).exists())

    def test_delete_message_reports_removed_fleet_groups(self):
        """US-002: komunikat po usunięciu mówi prawdę o usuniętych grupach floty mieszanej."""
        from scenario.models import Scenario, ScenarioFleet
        sc = Scenario.objects.create(name="S")
        ScenarioFleet.objects.create(scenario=sc, equipment=self.own, units=2)
        self.client.force_login(self.users["autor"])
        r = self.client.post(reverse("equipment:delete", args=[self.own.pk]), follow=True)
        self.assertContains(r, "Usunięto też grupy floty mieszanej z tym sprzętem: 1.")
        self.assertFalse(ScenarioFleet.objects.filter(scenario=sc).exists())
