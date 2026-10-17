"""Animacja przepływów w widoku 3D modelu: endpoint sceny dla odtwarzacza three.js
(ta sama scena co eksport do Blendera) + panel sterowania w widoku modelu."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from twin.models import (
    WarehouseHallFeature, WarehouseModel,
    WarehouseModelRack,
)
from twin.blender_scene import FORMAT
from twin.views.warehouse_blender import MAX_PICKERS, _clamped


class ClampTests(SimpleTestCase):
    def test_clamps_and_defaults(self):
        self.assertEqual(_clamped("99", 6, 1, MAX_PICKERS), MAX_PICKERS)
        self.assertEqual(_clamped("0", 6, 1, MAX_PICKERS), 1)
        self.assertEqual(_clamped("abc", 6, 1, MAX_PICKERS), 6)
        self.assertEqual(_clamped(None, 3, 0, 10), 3)


class FlowSceneEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("fl", password="x")
        cls.user.groups.add(Group.objects.get_or_create(name="Projektant")[0])  # parametry sceny ustawia Projektant
        cls.wm = WarehouseModel.objects.create(name="Hala", floor_width_m=30, floor_depth_m=20)
        for i, y in enumerate((3, 8), start=1):
            WarehouseModelRack.objects.create(model=cls.wm, zone="B0", rack_id=f"0{i}",
                                              n_bays=4, n_levels=3, x_m=4, y_m=y)
        WarehouseHallFeature.objects.create(model=cls.wm, kind="dock", label="Dok A",
                                            x_m=5, y_m=17, width_m=3, depth_m=2)

    def setUp(self):
        self.client.force_login(self.user)

    def _get(self, **params):
        return self.client.get(reverse("twin:warehouse_model_flow_json", args=[self.wm.pk]), params)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self._get().status_code, 302)

    def test_inline_json_same_format_as_blender_export(self):
        r = self._get(batch="demo")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Content-Disposition", r)          # fetch w przeglądarce, nie pobieranie
        sc = r.json()
        self.assertEqual(sc["format"], FORMAT)
        self.assertEqual(sc["source"]["picking"], "demo")
        self.assertTrue(sc["agents"] and sc["duration"] > 0)

    def test_viewer_gets_default_cached_scene(self):
        """Przegląd SEC (2), Z-3: Podgląd/gość nie zleca liczenia tras — parametry domyślne, scena z pamięci podręcznej."""
        from unittest import mock

        from django.core.cache import cache

        from twin.views import warehouse_blender as v
        cache.clear()
        viewer = get_user_model().objects.create_user("zarzad", password="x")
        viewer.groups.add(Group.objects.get_or_create(name="Podgląd")[0])
        self.client.force_login(viewer)
        with mock.patch.object(v, "build_scene_for_model", wraps=v.build_scene_for_model) as spy:
            for _ in range(3):
                self.assertEqual(self._get(forklifts="10", pickers="10", picks="25").status_code, 200)
        self.assertEqual(spy.call_count, 1)                                    # liczone raz, potem z pamięci
        self.assertNotIn("max_picks", spy.call_args.kwargs)                    # parametry z adresu pominięte

    def test_forklifts_param_and_no_pallets(self):
        sc = self._get(batch="demo", forklifts="0", pallets="0").json()
        self.assertFalse([a for a in sc["agents"] if a["kind"] == "forklift"])
        self.assertEqual(sc["pallets"], [])
        self.assertIsNone(sc["stock_stats"])

    def test_blender_export_still_downloads(self):
        r = self.client.get(reverse("twin:warehouse_model_blender_json", args=[self.wm.pk]))
        self.assertIn("attachment", r["Content-Disposition"])


class FlowPlayerPanelTests(TestCase):
    def test_model_view_has_player_panel_and_sources(self):
        user = get_user_model().objects.create_user("fv", password="x")
        user.groups.add(Group.objects.get_or_create(name="Podgląd")[0])  # _planner wymaga roli
        wm = WarehouseModel.objects.create(name="Hala", floor_width_m=30, floor_depth_m=20)
        self.client.force_login(user)
        r = self.client.get(reverse("twin:warehouse_model_view", args=[wm.pk]))
        self.assertContains(r, 'id="flow-player"')
        self.assertContains(r, "Załaduj animację")
        self.assertContains(r, reverse("twin:warehouse_model_flow_json", args=[wm.pk]))
        self.assertContains(r, "twin/js/flow-player.js")
        self.assertContains(r, "Symulacja demo")


class ViewerSceneFilterTests(SimpleTestCase):
    def test_simulation_batch_name_removed_for_viewer(self):
        """Przegląd SEC (5): nazwa importu zadań w scenie symulacji nie trafia do Podglądu."""
        from twin.views.warehouse_blender import _for_viewer
        sc = _for_viewer({"source": {"simulation": {"hour": 8, "batch": "Import marzec", "day": "2026-03-02"}}})
        self.assertEqual(sc["source"]["simulation"], {"hour": 8, "day": "2026-03-02"})
