"""Edycja wariantu hali blokami (plan 2026-10-02, etap 4)."""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from twin.models import WarehouseModel
from twin.design_generator import generate
from twin.model_edit import apply_zone_edit, collisions, fit_floor, zone_summary
from twin.tests.test_design_sim import RACKS


def _copy():
    return [dict(r) for r in RACKS]


class ModelEditTests(SimpleTestCase):
    def test_generated_hall_has_no_collisions(self):
        self.assertEqual(collisions(_copy()), [])

    def test_zone_summary(self):
        z = {s["zone"]: s for s in zone_summary(RACKS)}
        self.assertEqual(set(z), {"V", "K1"})
        self.assertEqual(z["V"]["rows"], sum(r["zone"] == "V" for r in RACKS))

    def test_shift_moves_only_that_zone(self):
        racks = _copy()
        changed = apply_zone_edit(racks, "K1", dx=5, dy=-1)
        self.assertTrue(changed and all(r["zone"] == "K1" for r in changed))
        before = {(r["zone"], r["rack_id"]): r for r in RACKS}
        for r in racks:
            b = before[(r["zone"], r["rack_id"])]
            self.assertEqual((r["x"], r["y"]), (round(b["x"] + 5, 2), round(b["y"] - 1, 2)) if r["zone"] == "K1"
                             else (b["x"], b["y"]))

    def test_longer_rows_keep_bay_width_and_can_collide(self):
        racks = _copy()
        v = next(r for r in racks if r["zone"] == "V")
        bay_w = v["width"] / v["n_bays"]
        apply_zone_edit(racks, "V", n_bays=v["n_bays"] + 40)
        self.assertAlmostEqual(v["width"] / v["n_bays"], bay_w, places=3)
        self.assertTrue(collisions(racks))                  # rzędy V wjeżdżają w półki K1

    def test_fit_floor_grows_with_racks(self):
        racks = _copy()
        apply_zone_edit(racks, "K1", dx=50)
        w, _ = fit_floor(racks, 10, 10)
        self.assertGreater(w, max(r["x"] + r["width"] for r in racks))


class VariantEditViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from twin.views.warehouse_generator import _save

        cls.wm = _save("Bazowy", generate(pallet_positions=6000, carton_locations=3000))

    def setUp(self):
        get_user_model().objects.create_superuser(username="e", password="x")
        self.client.post("/login/", {"username": "e", "password": "x"})

    def test_copy_keeps_original(self):
        n = self.wm.racks.count()
        r = self.client.post(f"/magazyn/model/{self.wm.pk}/kopia/")
        copy = WarehouseModel.objects.exclude(pk=self.wm.pk).get()
        self.assertRedirects(r, f"/magazyn/model/{copy.pk}/edytor/", fetch_redirect_response=False)
        self.assertEqual((copy.racks.count(), self.wm.racks.count()), (n, n))
        self.assertEqual(copy.features.count(), self.wm.features.count())
        self.assertIn("przyszły layout", copy.name)

    def test_copy_keeps_hall_structure(self):
        """Kopia „przyszłego layoutu” niesie konstrukcję hali z E2b: wysokość, słupy, sprzęt regałów."""
        cols = {"pitch_x": 12, "pitch_y": 24, "offset_x": 0, "offset_y": 0, "size": 0.6, "removed": [[0, 0]], "extra": []}
        WarehouseModel.objects.filter(pk=self.wm.pk).update(clear_height_m=11.5, columns=cols)
        self.wm.racks.filter(zone="V").update(equipment="vna")
        self.client.post(f"/magazyn/model/{self.wm.pk}/kopia/")
        copy = WarehouseModel.objects.exclude(pk=self.wm.pk).get()
        self.assertEqual((copy.clear_height_m, copy.columns), (11.5, cols))
        self.assertEqual(set(copy.racks.filter(zone="V").values_list("equipment", flat=True)), {"vna"})

    def test_zone_edit_saves_and_deletes(self):
        k1_x = self.wm.racks.filter(zone="K1").first().x_m
        self.assertContains(self.client.get(f"/magazyn/model/{self.wm.pk}/strefy/"), "Edycja stref regałów")
        r = self.client.post(f"/magazyn/model/{self.wm.pk}/strefy/", {
            "dx_K1": "2,5", "dy_K1": "0", "bays_K1": "", "levels_K1": "4",
            "dx_V": "0", "dy_V": "0", "bays_V": "", "levels_V": "", "del_V": "1",
            "floor_w": "", "floor_d": ""})
        self.assertRedirects(r, f"/magazyn/model/{self.wm.pk}/view/", fetch_redirect_response=False)
        self.assertFalse(self.wm.racks.filter(zone="V").exists())
        k1 = self.wm.racks.filter(zone="K1")
        self.assertEqual({x.n_levels for x in k1}, {4})
        self.assertAlmostEqual(k1.first().x_m, k1_x + 2.5)

    def test_negative_shift_is_rejected(self):
        before = list(self.wm.racks.values_list("x_m", flat=True))
        self.client.post(f"/magazyn/model/{self.wm.pk}/strefy/", {"dx_V": "-9999", "dx_K1": "0"})
        self.client.post(f"/magazyn/model/{self.wm.pk}/strefy/", {"dx_V": "-400", "dx_K1": "0"})
        self.assertEqual(list(self.wm.racks.values_list("x_m", flat=True)), before)

    def test_rejected_edit_keeps_typed_values(self):
        """US-021: odrzucona edycja stref wraca z wpisanymi wartościami, nie z pustym formularzem."""
        r = self.client.post(f"/magazyn/model/{self.wm.pk}/strefy/",
                             {"dx_V": "-400", "dy_V": "1,5", "levels_K1": "7", "del_K1": "1", "floor_w": "123"})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "poza halę", status_code=400)
        for value in ('name="dx_V" value="-400"', 'name="dy_V" value="1,5"', 'name="levels_K1" value="7"',
                      'value="123"'):
            self.assertContains(r, value, status_code=400)
        self.assertRegex(r.content.decode(), r'name="del_K1" value="1" checked')

    def test_view_has_variant_buttons(self):
        r = self.client.get(f"/magazyn/model/{self.wm.pk}/view/")
        self.assertContains(r, "Utwórz przyszły layout (kopia)")
        self.assertContains(r, f"/magazyn/model/{self.wm.pk}/strefy/")
