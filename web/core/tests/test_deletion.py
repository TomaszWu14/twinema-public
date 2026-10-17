"""US-004: usunięcie hali, scenariusza i sprzętu wymaga potwierdzenia, które wymienia skutki."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from equipment.models import Equipment
from scenario.models import Scenario, ScenarioFleet, Showcase
from twin.models import WarehouseModel


class DeleteConfirmationTests(TestCase):
    def setUp(self):
        self.designer = User.objects.create_user("proj", password="x")
        self.designer.groups.add(Group.objects.get_or_create(name=GROUP_DESIGNER)[0])
        self.viewer = User.objects.create_user("zarzad", password="x")
        self.viewer.groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])
        self.client.force_login(self.designer)
        self.wm = WarehouseModel.objects.create(name="Hala do usunięcia", floor_width_m=40, floor_depth_m=30)
        self.wm.racks.create(zone="A", rack_id="001", n_bays=5, n_levels=3, bay_width_cm=270, depth_cm=110,
                             x_m=5, y_m=5)
        Showcase.objects.create(title="Pokaz", model=self.wm)
        self.sc = Scenario.objects.create(name="Scenariusz do usunięcia")
        self.eq = Equipment.objects.create(kind="reach", name="Mój reach", capacity_kg=1500, speed_loaded_kmh=10,
                                           speed_empty_kmh=11, created_by=self.designer)
        ScenarioFleet.objects.create(scenario=self.sc, equipment=self.eq, units=2)

    def test_hall_confirmation_lists_cascade_and_get_deletes_nothing(self):
        page = self.client.get(reverse("twin:warehouse_model_delete", args=[self.wm.pk]))
        self.assertContains(page, "Hala do usunięcia")                       # nazwa modelu (wcześniej pusta)
        self.assertContains(page, "regały: <strong>1</strong>", html=False)
        self.assertContains(page, "prezentacje 3D: <strong>1</strong>", html=False)
        self.assertTrue(WarehouseModel.objects.filter(pk=self.wm.pk).exists())
        self.client.post(reverse("twin:warehouse_model_delete", args=[self.wm.pk]))
        self.assertFalse(WarehouseModel.objects.filter(pk=self.wm.pk).exists())

    def test_scenario_confirmation_then_delete(self):
        page = self.client.get(reverse("scenario:delete", args=[self.sc.pk]))
        self.assertContains(page, "grupy floty mieszanej: <strong>1</strong>", html=False)
        self.assertTrue(Scenario.objects.filter(pk=self.sc.pk).exists())
        self.assertContains(self.client.get(reverse("scenario:detail", args=[self.sc.pk])),
                            f'href="{reverse("scenario:delete", args=[self.sc.pk])}"')
        self.client.post(reverse("scenario:delete", args=[self.sc.pk]))
        self.assertFalse(Scenario.objects.filter(pk=self.sc.pk).exists())

    def test_equipment_confirmation_lists_fleet_groups(self):
        page = self.client.get(reverse("equipment:delete", args=[self.eq.pk]))
        self.assertContains(page, "grupy floty mieszanej w scenariuszach: <strong>1</strong>", html=False)
        self.assertTrue(Equipment.objects.filter(pk=self.eq.pk).exists())

    def test_viewer_cannot_open_confirmation(self):
        self.client.force_login(self.viewer)
        for url in (reverse("twin:warehouse_model_delete", args=[self.wm.pk]),
                    reverse("scenario:delete", args=[self.sc.pk]), reverse("equipment:delete", args=[self.eq.pk])):
            self.assertEqual(self.client.get(url).status_code, 403, url)
