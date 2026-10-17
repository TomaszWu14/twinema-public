"""API edytora layoutu: role, sprawdzenie bez zapisu, zapis (tworzy/aktualizuje/usuwa/przenosi), 409, 422."""
import json

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from twin.models import WarehouseHallFeature, WarehouseModel, WarehouseModelRack


class LayoutApiTests(TestCase):
    def setUp(self):
        self.wm = WarehouseModel.objects.create(name="Hala", floor_width_m=60, floor_depth_m=40)
        self.r1 = self.wm.racks.create(zone="V", rack_id="001", n_bays=4, n_levels=4, x_m=5, y_m=5)
        self.r2 = self.wm.racks.create(zone="V", rack_id="002", n_bays=4, n_levels=4, x_m=5, y_m=12)
        self.dock = self.wm.features.create(kind="dock", label="Dok 1", x_m=0, y_m=30, width_m=4, depth_m=3.5)
        self.designer = User.objects.create_user("proj", password="x")
        self.designer.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.viewer = User.objects.create_user("zarzad", password="x")
        self.viewer.groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.client.force_login(self.designer)

    def _get(self):
        return self.client.get(reverse("twin:warehouse_layout_json", args=[self.wm.pk])).json()

    def _post(self, name, data):
        return self.client.post(reverse(f"twin:warehouse_layout_{name}", args=[self.wm.pk]),
                                json.dumps(data), content_type="application/json")

    def test_get_layout(self):
        data = self._get()
        self.assertEqual([r["rack_id"] for r in data["racks"]], ["001", "002"])
        self.assertEqual(data["features"][0]["kind"], "dock")
        self.assertEqual(data["feature_kinds"]["staging"], "Pole odkładcze")
        self.assertTrue(data["version"])

    def test_check_does_not_save(self):
        data = self._get()
        data["racks"][1]["y"] = 5.5                                     # wjeżdża w pierwszy regał
        r = self._post("check", data).json()
        self.assertEqual([i["code"] for i in r["issues"]], ["collision"])
        self.assertGreater(r["kpi"]["pallet_positions"], 0)
        self.r2.refresh_from_db()
        self.assertEqual(self.r2.y_m, 12)

    def test_viewer_reads_but_cannot_check_or_save(self):
        self.client.force_login(self.viewer)
        data = self._get()
        self.assertEqual(self._post("check", data).status_code, 403)
        self.assertEqual(self._post("save", data).status_code, 403)

    def test_bad_json_and_bad_values_are_400(self):
        r = self.client.post(reverse("twin:warehouse_layout_check", args=[self.wm.pk]), "{nie",
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        data = self._get()
        data["racks"][0]["n_bays"] = -1
        self.assertIn("n_bays", self._post("check", data).json()["error"])

    def test_save_updates_creates_deletes_and_moves_between_zones(self):
        data = self._get()
        data["racks"][0].update(x=8.0, angle=90.0)
        data["racks"][1].update(zone="K1", rack_id="001")              # przeniesienie do innej strefy
        data["racks"].append({**data["racks"][0], "id": None, "zone": "V", "rack_id": "003", "x": 30.0,
                              "y": 5.0, "angle": 0.0})
        data["features"] = [{"kind": "staging", "label": "Pole przyjęć", "x": 40, "y": 30, "width": 8,
                             "depth": 5, "angle": 0}]                    # dok usunięty, pole dodane
        r = self._post("save", data)
        self.assertEqual(r.status_code, 200, r.content)
        self.r1.refresh_from_db()
        self.assertEqual((self.r1.x_m, self.r1.angle_deg), (8.0, 90.0))
        self.assertEqual(sorted(self.wm.racks.values_list("zone", "rack_id")),
                         [("K1", "001"), ("V", "001"), ("V", "003")])
        self.assertEqual(self.wm.racks.get(zone="K1").pk, self.r2.pk)  # ten sam regał, nowy adres
        self.assertFalse(WarehouseHallFeature.objects.filter(pk=self.dock.pk).exists())
        self.assertEqual(self.wm.features.get().kind, "staging")
        self.assertNotEqual(r.json()["version"], data["version"])

    def test_save_swaps_addresses(self):
        data = self._get()
        data["racks"][0]["rack_id"], data["racks"][1]["rack_id"] = "002", "001"
        self.assertEqual(self._post("save", data).status_code, 200)
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.rack_id, "002")

    def test_errors_block_save_warnings_do_not(self):
        data = self._get()
        data["racks"][1]["y"] = 5.5
        r = self._post("save", data)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["issues"][0]["code"], "collision")
        data = self._get()
        data["racks"][1]["y"] = 7.6                                     # za wąska alejka = ostrzeżenie
        r = self._post("save", data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([i["code"] for i in r.json()["issues"]], ["aisle"])

    def test_issue_indexes_point_to_returned_order(self):
        data = self._get()
        data["racks"][1]["y"] = 7.6                                     # ostrzeżenie alejki V-001 / V-002
        extra = {**data["racks"][0], "id": None, "zone": "A", "rack_id": "001", "x": 40, "y": 30}
        data["racks"] = [data["racks"][1], data["racks"][0], extra]     # kolejność klienta ≠ sortowanie
        r = self._post("save", data).json()
        issue = next(i for i in r["issues"] if i["code"] == "aisle")
        names = {f'{r["racks"][k]["zone"]}-{r["racks"][k]["rack_id"]}' for k in issue["racks"]}
        self.assertEqual(names, {"V-001", "V-002"})

    def test_stale_version_is_409(self):
        data = self._get()
        self._post("save", self._get())                                 # ktoś inny zapisał w międzyczasie
        data["racks"][0]["x"] = 9.0
        r = self._post("save", data)
        self.assertEqual(r.status_code, 409)
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.x_m, 5)

    def test_foreign_ids_rejected(self):
        other = WarehouseModel.objects.create(name="Inna")
        alien = other.racks.create(zone="X", rack_id="1")
        data = self._get()
        data["racks"][0]["id"] = alien.pk
        self.assertEqual(self._post("save", data).status_code, 409)
        self.assertEqual(WarehouseModelRack.objects.get(pk=alien.pk).zone, "X")


class LayoutEditorPageTests(TestCase):
    """Ekran edytora (E2): tylko Projektant/Administratorzy, konfiguracja dla modułu JS, linki."""

    def setUp(self):
        self.wm = WarehouseModel.objects.create(name="Hala", floor_width_m=60, floor_depth_m=40)
        self.designer = User.objects.create_user("proj", password="x")
        self.designer.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.viewer = User.objects.create_user("zarzad", password="x")
        self.viewer.groups.add(Group.objects.create(name=GROUP_VIEWER))

    def test_designer_gets_editor_with_api_config(self):
        self.client.force_login(self.designer)
        r = self.client.get(reverse("twin:warehouse_layout_editor", args=[self.wm.pk]))
        self.assertEqual(r.status_code, 200)
        cfg = json.loads(r.content.decode().split('id="le-config" type="application/json">')[1].split("</script>")[0])
        self.assertEqual(cfg["urls"]["check"], reverse("twin:warehouse_layout_check", args=[self.wm.pk]))
        self.assertEqual(cfg["urls"]["save"], reverse("twin:warehouse_layout_save", args=[self.wm.pk]))
        self.assertEqual(cfg["limits"]["n_levels"], [1, 40])
        self.assertEqual(cfg["aisle"], 3.0)
        self.assertContains(r, "twin/js/layout-editor.js")
        self.assertContains(r, 'aria-live="polite"')

    def test_viewer_has_no_editor_and_no_link(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("twin:warehouse_layout_editor", args=[self.wm.pk])).status_code, 403)
        url = reverse("twin:warehouse_layout_editor", args=[self.wm.pk])
        self.assertNotContains(self.client.get(reverse("twin:warehouse_model_view", args=[self.wm.pk])), url)

    def test_links_from_model_view_and_list(self):
        self.client.force_login(self.designer)
        url = reverse("twin:warehouse_layout_editor", args=[self.wm.pk])
        self.assertContains(self.client.get(reverse("twin:warehouse_model_view", args=[self.wm.pk])), url)
        self.assertContains(self.client.get(reverse("twin:warehouse_model_list")), url)

    def test_anonymous_redirects_to_login(self):
        r = self.client.get(reverse("twin:warehouse_layout_editor", args=[self.wm.pk]))
        self.assertEqual(r.status_code, 302)

    def test_editor_has_3d_preview(self):
        """E3: podgląd 3D obok planu — three.js z vendora (importmap, bez CDN), przełącznik układu,
        sonda WebGL, link do animacji przepływów; przycisk kopii „przyszłego layoutu” w widoku i na liście."""
        self.client.force_login(self.designer)
        r = self.client.get(reverse("twin:warehouse_layout_editor", args=[self.wm.pk]))
        self.assertContains(r, 'type="importmap">')
        self.assertContains(r, "/static/twin/vendor/three.module.js")
        self.assertNotContains(r, "cdn.")
        for marker in ('id="le-3d-canvas"', 'data-le-mode="split"', 'id="le-3d-sel"', "__tw3dNoWebGL",
                       "Zobacz animację przepływów"):
            self.assertContains(r, marker)
        # Pełny ekran (wspólny static/twin/js/fullscreen.js): obszar roboczy edytora, scena 3D i plan 2D modelu.
        for marker in ('id="le-fs" data-fs aria-pressed="false"', 'id="le-work"', 'id="le-fs-live" aria-live="polite"'):
            self.assertContains(r, marker)
        view = self.client.get(reverse("twin:warehouse_model_view", args=[self.wm.pk]))
        for marker in ('id="fs-3d" data-fs', 'id="fs-2d" data-fs', 'id="fs-live" aria-live="polite"',
                       "twin/js/fullscreen.js"):
            self.assertContains(view, marker)
        copy = reverse("twin:warehouse_model_copy", args=[self.wm.pk])
        self.assertContains(self.client.get(reverse("twin:warehouse_model_view", args=[self.wm.pk])), copy)
        self.assertContains(self.client.get(reverse("twin:warehouse_model_list")), copy)
