"""Moduł Dane z bazą: zapis importów, demo, widoki i podpięcie do bliźniaka (scena, dzień projektowy)."""
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from masterdata import importers, services
from masterdata.demo import demo_stock
from masterdata.models import ImportLog, Material, StockItem
from twin.blender_scene import build_scene_for_model
from twin.design_day import load_groups
from twin.models import WarehouseLocationMasterBatch, WarehouseModel
from core.jobs import run_pending
from django.test import override_settings
import tempfile
from pathlib import Path


TMP_MEDIA = tempfile.mkdtemp(prefix="twinema-md-")


def _csv(text):
    return text.encode("utf-8")


class ImportServiceTests(TestCase):
    def test_materials_upsert_and_report(self):
        Material.objects.create(code="M1", name="stara", group="A")
        log = services.import_file("materials", "m.csv", _csv(
            "Kod;Nazwa;Grupa towarowa;Karton waga [kg]\nM1;nowa;B;2,5\nM2;druga;B;x\nM3;trzecia;C;1\n"))
        self.assertEqual((log.rows_total, log.rows_ok, log.rows_rejected), (3, 2, 1))
        self.assertEqual(log.rejects, [{"row": 3, "reason": "karton waga [kg]: „x” to nie liczba"}])
        self.assertEqual(Material.objects.get(code="M1").name, "nowa")
        self.assertEqual(Material.objects.count(), 2)

    def test_missing_required_column_saves_nothing(self):
        with self.assertRaisesMessage(importers.ImportFileError, "Brak wymaganych kolumn: lokalizacja"):
            services.import_file("stock", "s.csv", _csv("Materiał;Ilość\nM1;3\n"))
        self.assertFalse(ImportLog.objects.exists())

    def test_locations_create_new_active_master(self):
        old = WarehouseLocationMasterBatch.objects.create(name="stary", is_active=True)
        services.import_file("locations", "lok.csv", _csv("Lokalizacja;Typ\nB0-01-100A;0020\nB0-01-100C;0010\n"))
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        batch = WarehouseLocationMasterBatch.objects.get(is_active=True)
        self.assertEqual(dict(batch.locations.values_list("location_code", "level")),
                         {"B0-01-100A": 1, "B0-01-100C": 3})        # poziom z litery kodu

    def test_latest_stock_import_is_current_stock(self):
        services.import_file("stock", "s1.csv", _csv("Lokalizacja;Materiał;Ilość\nL1;M1;1\n"))
        services.import_file("stock", "s2.csv", _csv("Lokalizacja;Materiał;Ilość;HU\nL2;M2;4;HU1\n"))
        Material.objects.create(code="M2", name="Paleta testowa")
        self.assertEqual(services.stock_for_scene(), [
            {"location": "L2", "sku": "M2", "name": "Paleta testowa", "qty": 4.0, "unit": "", "hu": "HU1",
             "lot": "", "expiry": None}])

    def test_groups_for_design_day(self):
        self.assertIsNone(load_groups(["M1"]))                      # brak materiałów → bez podziału
        Material.objects.create(code="1005796", group="Elektronika")
        Material.objects.create(code="M9")
        self.assertEqual(load_groups(["1005796", "0001005796", "M9", "NIEMA"]),
                         {"1005796": "Elektronika", "0001005796": "Elektronika", "M9": None, "NIEMA": None})


class DemoAndSceneTests(TestCase):
    def test_demo_stock_lands_as_pallets_in_scene(self):
        wm = WarehouseModel.objects.create(name="Hala demo", floor_width_m=40, floor_depth_m=30)
        for i, y in enumerate((4, 10), start=1):
            wm.racks.create(zone="V", rack_id=f"{i:03d}", n_bays=6, n_levels=4, x_m=4, y_m=y)
        n_mat, log = services.load_demo(wm, fill=1.0)
        self.assertEqual(n_mat, 3000)
        self.assertEqual(log.rows_ok, 2 * 6 * 4)
        self.assertEqual(StockItem.objects.filter(log=log).values("location_code").distinct().count(), 48)
        scene = build_scene_for_model(wm, None, with_pallets=True, forklifts=0, max_pickers=1, max_picks=1)
        self.assertEqual(len(scene["pallets"]), 48)
        self.assertEqual({p["level"] for p in scene["pallets"]}, {1, 2, 3, 4})


class DemoStockTests(SimpleTestCase):
    def test_wide_bays_hold_several_pallets_per_level(self):
        rack = {"zone": "V", "rack_id": "001", "n_bays": 2, "n_levels": 3, "width": 5.4}   # 2 × 2,7 m
        codes = [s["location_code"] for s in demo_stock([rack], fill=1.0)]
        self.assertEqual(len(codes), 2 * 3 * 3)                        # 3 palety na belce × 3 poziomy
        self.assertEqual(len(set(codes)), len(codes))
        self.assertIn("V-001-102C", codes)                            # gniazdo 10, pozycja 2, poziom 3

    def test_fill_and_seed_are_deterministic(self):
        rack = {"zone": "V", "rack_id": "001", "n_bays": 20, "n_levels": 5, "width": 18}
        a, b = demo_stock([rack], fill=0.5, seed=3), demo_stock([rack], fill=0.5, seed=3)
        self.assertEqual(a, b)
        self.assertTrue(0.3 < len(a) / 100 < 0.7)


class DaneViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.designer = User.objects.create_user("proj", password="x")
        cls.designer.groups.add(Group.objects.get_or_create(name=GROUP_DESIGNER)[0])
        cls.viewer = User.objects.create_user("widz", password="x")
        cls.viewer.groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])

    def _upload(self, kind, name, content):
        return self.client.post(reverse("masterdata:upload", args=[kind]),
                                {"file": SimpleUploadedFile(name, content)})

    def test_home_lists_imports_and_hides_upload_for_viewer(self):
        self.client.force_login(self.viewer)
        r = self.client.get(reverse("masterdata:home"))
        self.assertContains(r, "Historia importów")
        self.assertNotContains(r, 'name="file"')
        self.assertEqual(self._upload("materials", "m.csv", _csv("Kod\nA\n")).status_code, 403)
        self.assertFalse(Material.objects.exists())

    @override_settings(MEDIA_ROOT=TMP_MEDIA)
    def test_designer_upload_runs_in_queue_and_links_report_with_rejects(self):
        self.client.force_login(self.designer)
        r = self._upload("materials", "m.csv", _csv("Kod;Nazwa\nA1;Śruba\n;bez kodu\n"))
        self.assertRedirects(r, reverse("masterdata:home"), fetch_redirect_response=False)
        self.assertFalse(ImportLog.objects.exists())                    # T-1: import liczy worker kolejki
        run_pending()
        log = ImportLog.objects.get()
        home = self.client.get(reverse("masterdata:home"))
        self.assertContains(home, "zapisano 1 z 2 wierszy")
        self.assertContains(home, reverse("masterdata:log_detail", args=[log.pk]))
        self.assertEqual(list(Path(TMP_MEDIA, "masterdata_uploads").iterdir()), [])   # plik usunięty po imporcie
        r = self.client.get(reverse("masterdata:log_detail", args=[log.pk]))
        self.assertContains(r, "brak: kod materiału")
        self.assertContains(r, "Rozpoznane kolumny")

    @override_settings(MEDIA_ROOT=TMP_MEDIA)
    def test_bad_file_shows_message_not_500(self):
        self.client.force_login(self.designer)
        r = self._upload("stock", "s.csv", _csv("Materiał\nM1\n"))
        self.assertRedirects(r, reverse("masterdata:home"), fetch_redirect_response=False)
        run_pending()
        self.assertContains(self.client.get(reverse("masterdata:home")), "Brak wymaganych kolumn")

    def test_template_download_and_materials_search(self):
        self.client.force_login(self.viewer)
        r = self.client.get(reverse("masterdata:template", args=["stock"]))
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertTrue(r.content.decode("utf-8").startswith("﻿lokalizacja;materiał"))
        Material.objects.create(code="ZZ-80", name="Wiertarka", group="Narzędzia")
        Material.objects.create(code="AA-1", name="Kubek", group="AGD")
        self.assertEqual(self.client.get(reverse("masterdata:materials")).status_code, 403)  # #25: bez danych źródłowych
        self.client.force_login(self.designer)
        r = self.client.get(reverse("masterdata:materials"), {"q": "wiert"})
        self.assertContains(r, "ZZ-80")
        self.assertNotContains(r, "AA-1")

    def test_demo_button_requires_model_and_designer(self):
        wm = WarehouseModel.objects.create(name="Hala")
        wm.racks.create(zone="V", rack_id="001", n_bays=2, n_levels=2, x_m=2, y_m=2)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(reverse("masterdata:demo"), {"model": wm.pk}).status_code, 403)
        self.client.force_login(self.designer)
        r = self.client.post(reverse("masterdata:demo"), {"model": wm.pk})
        self.assertRedirects(r, reverse("twin:warehouse_model_view", args=[wm.pk]), fetch_redirect_response=False)
        self.assertTrue(StockItem.objects.exists())
