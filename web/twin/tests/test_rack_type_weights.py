"""Typy regałów A/B/C/D: nośność per poziom (level_weights) — zapis w edytorze,
serializacja do rack_types i etykiety kg w widoku 3D."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from twin import models as m


class RackTypeWeightsTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_superuser(username="b", password="x")
        self.client.post("/login/", {"username": "b", "password": "x"})

    def test_model_stores_level_weights(self):
        rt = m.WarehouseRackType.objects.create(code="A", name="Typ A",
                                                level_weights={"1": 1000, "2": 300})
        rt.refresh_from_db()
        self.assertEqual(rt.level_weights, {"1": 1000, "2": 300})

    def test_editor_saves_level_weights(self):
        url = reverse("twin:warehouse_rack_type_new")
        self.client.post(url, {
            "code": "B", "name": "Typ B",
            "level_1_height": "2400", "level_1_weight": "1000",
            "level_2_height": "1200", "level_2_weight": "300",
            "width_mm": "800", "manip_mm": "900", "depth_mm": "1100",
            "max_weight_kg": "1200", "max_volume_m3": "2.5",
            "color_hex": "#f59e0b", "level_cols_json": "{}",
        })
        rt = m.WarehouseRackType.objects.get(code="B")
        self.assertEqual(rt.level_weights, {"1": 1000, "2": 300})
        self.assertEqual(rt.level_heights, {"1": 2400, "2": 1200})

    def test_editor_get_200(self):
        rt = m.WarehouseRackType.objects.create(code="C", name="Typ C",
                                                level_weights={"1": 1000})
        r = self.client.get(reverse("twin:warehouse_rack_type_edit", args=[rt.pk]))
        self.assertEqual(r.status_code, 200)



class RackTypeFormKeepsValuesTests(TestCase):
    """US-021: błąd walidacji typu regału nie kasuje wpisanych danych."""

    def setUp(self):
        get_user_model().objects.create_superuser(username="b", password="x")
        self.client.post("/login/", {"username": "b", "password": "x"})
        m.WarehouseRackType.objects.create(code="A", name="Typ A")

    def _post(self, url, **over):
        data = {"code": "A", "name": "Mój nowy typ", "description": "opis do zachowania", "width_mm": "850",
                "manip_mm": "950", "depth_mm": "1200", "max_weight_kg": "1300", "max_volume_m3": "2.8",
                "color_hex": "#123456", "level_1_height": "2400", "level_1_weight": "900", "level_cols_json": "{}"}
        return self.client.post(url, {**data, **over})

    def test_duplicate_code_shows_form_with_typed_values(self):
        r = self._post(reverse("twin:warehouse_rack_type_new"))
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "już istnieje", status_code=400)
        for value in ("Mój nowy typ", "opis do zachowania", 'value="850"', "#123456", '"1": "900"'):
            self.assertContains(r, value, status_code=400)
        self.assertContains(r, reverse("twin:warehouse_rack_type_new"), status_code=400)   # nadal tworzenie
        self.assertEqual(m.WarehouseRackType.objects.count(), 1)

    def test_bad_number_on_edit_keeps_edit_target(self):
        rt = m.WarehouseRackType.objects.create(code="B", name="Typ B")
        url = reverse("twin:warehouse_rack_type_edit", args=[rt.pk])
        r = self._post(url, code="B", width_mm="szeroko")
        self.assertContains(r, "Błąd wartości", status_code=400)
        self.assertContains(r, 'value="szeroko"', status_code=400)
        self.assertContains(r, url, status_code=400)
        rt.refresh_from_db()
        self.assertEqual(rt.name, "Typ B")

    def test_bad_columns_json_is_shown_back(self):
        r = self._post(reverse("twin:warehouse_rack_type_new"), code="Z", level_cols_json="{zły json")
        self.assertContains(r, "{zły json", status_code=400)
