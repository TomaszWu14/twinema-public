"""Animacja dnia (S4): miejsca z layoutu, wąskie gardła → miejsca i okna czasu, strona odtwarzacza, zdarzenia."""
from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from equipment.models import Equipment
from scenario.models import Scenario, ScenarioRun
from scenario.views_play import bottleneck_focus, layout_places, peak_index
from twin.models import WarehouseModel
from core.jobs import run_pending

FLOOR = {"width": 80, "depth": 50}
FEATS = [
    {"id": 1, "kind": "dock", "label": "Dok kontenerowy 1", "x": 0, "y": 5, "width": 3.5, "depth": 4, "angle": 0},
    {"id": 2, "kind": "dock", "label": "Dok FTL", "x": 0, "y": 15, "width": 3.5, "depth": 4, "angle": 0},
    {"id": 3, "kind": "dock", "label": "Dok wspólny", "x": 0, "y": 25, "width": 3.5, "depth": 4, "angle": 0},
    {"id": 4, "kind": "staging", "label": "Bufor przyjęć", "x": 6, "y": 5, "width": 10, "depth": 20, "angle": 0},
    {"id": 5, "kind": "station", "label": "Pakowanie paczek 1", "x": 40, "y": 40, "width": 4, "depth": 4, "angle": 0},
    {"id": 6, "kind": "station", "label": "Paletyzacja 1", "x": 6, "y": 30, "width": 4, "depth": 3.5, "angle": 0},
    {"id": None, "kind": "column", "label": "", "x": 20, "y": 20, "width": 0.5, "depth": 0.5, "angle": 0},
]


class PlacesTests(SimpleTestCase):
    def test_docks_point_outward_and_have_roles(self):
        p = layout_places(FEATS, FLOOR)
        self.assertEqual(p["docks"]["1"]["out"], (-1, 0))               # ściana x = 0 → na zewnątrz w −x
        self.assertEqual({k: d["role"] for k, d in p["docks"].items()},
                         {"1": "in_container", "2": "out", "3": "shared"})
        self.assertLess(p["gate"][0], 0)                                # brama przed ścianą doków
        self.assertEqual(p["docks"]["1"]["wall"], [0, 7.0])              # punkt doku na ścianie (auto stoi za nim)

    def test_gate_on_side_with_most_docks_not_inside_hall(self):
        # Doki na dwóch przeciwległych ścianach: średnia wypadała w środku hali → auta jechały przez halę.
        feats = FEATS + [{"id": 9, "kind": "dock", "label": "Dok wydań", "x": 76, "y": 20, "width": 3.5,
                          "depth": 4, "angle": 0}]
        p = layout_places(feats, FLOOR)
        self.assertEqual(p["docks"]["9"]["out"], (1, 0))
        self.assertEqual(p["docks"]["9"]["wall"], [80, 22.0])
        self.assertLess(p["gate"][0], 0)                                # 3 doki na ścianie x = 0 wygrywają
        self.assertEqual(len(p["staging_in"]), 1)
        self.assertEqual(p["staging_out"], [])
        self.assertEqual(len(p["pack"]), 1)
        self.assertEqual(len(p["palletize"]), 1)

    def test_bottleneck_maps_to_places_and_window(self):
        p = layout_places(FEATS, FLOOR)
        f = bottleneck_focus({"area": "Doki kontenerowe (IN)", "window": "06:00–09:30"}, p)
        self.assertEqual(f, {"t0": 6 * 3600, "t1": 9.5 * 3600, "keys": ["dock:1", "dock:3"]})   # wspólny też
        f = bottleneck_focus({"area": "Pakowanie i nadanie", "window": "14:00–22:00"}, p)
        self.assertEqual(f["keys"], ["pack"])
        f = bottleneck_focus({"area": "Pole odkładcze wydań", "window": ""}, p)
        self.assertEqual(f, {"t0": None, "t1": None, "keys": []})        # brak pola wydań w layoucie
        f = bottleneck_focus({"area": "Rozładunek", "window": "22:00–06:00"}, p)
        self.assertEqual((f["t0"], f["t1"]), (22 * 3600, 30 * 3600))      # przez północ

    def test_peak_index(self):
        tl = {"t": ["06:00", "06:15", "06:30"], "queue_in_container": [0, 2, 1], "staging_in": [1, 5, 9],
              "staging_out": [0, 0, 0]}
        self.assertEqual(peak_index(tl), 2)
        self.assertEqual(peak_index({"t": []}), 0)


class PlayViewTests(TestCase):
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
        self.wm.racks.create(zone="V", rack_id="001", n_bays=6, n_levels=4, x_m=30, y_m=10)
        self.client.post(reverse("scenario:simulate", args=[self.sc.pk]),
                         {"model": self.wm.pk, "day": "typical", "runs": 2})
        run_pending()                                   # US-007: symulację liczy worker kolejki
        self.run = ScenarioRun.objects.get()

    def test_events_have_s4_extensions(self):
        ev = self.client.get(reverse("scenario:run_events", args=[self.run.pk])).json()["events"]
        whats = {(e[2], e[3]) for e in ev}
        self.assertIn(("pallet", "loaded"), whats)                    # paleta znika z pola wydań na auto
        self.assertIn(("courier", "arrive"), whats)
        self.assertIn(("courier", "depart"), whats)
        packed = [e for e in ev if e[3] == "packed"]
        self.assertTrue(packed and all(len(e) == 6 and e[5] >= 1 for e in packed))   # liczba paczek

    def test_designer_and_viewer_see_player(self):
        url = reverse("scenario:run_play", args=[self.run.pk])
        for user in (self.designer, self.viewer):
            self.client.force_login(user)
            r = self.client.get(url)
            self.assertContains(r, 'id="dp-canvas"')
            self.assertContains(r, "day-player.js")
            self.assertContains(r, 'id="dp-fs"')
            self.assertContains(r, reverse("scenario:run_events", args=[self.run.pk]))
            self.assertContains(r, "Tabela godzinowa")
        detail = self.client.get(reverse("scenario:detail", args=[self.sc.pk]))
        self.assertContains(detail, url)                              # link „Animacja dnia” przy wyniku

    def test_fleet_kind_from_catalog_in_player_data(self):
        r = self.client.get(reverse("scenario:run_play", args=[self.run.pk]))
        self.assertContains(r, '"fleet_kind": ""')                      # bez floty z katalogu → domyślny model
        Scenario.objects.filter(pk=self.sc.pk).update(fleet_equipment=Equipment.objects.filter(kind="agv").first())
        r = self.client.get(reverse("scenario:run_play", args=[self.run.pk]))
        self.assertContains(r, '"fleet_kind": "agv"')

    def test_run_without_events_shows_message(self):
        ScenarioRun.objects.filter(pk=self.run.pk).update(events=[], has_events=False)
        r = self.client.get(reverse("scenario:run_play", args=[self.run.pk]))
        self.assertContains(r, "nie ma zapisanych zdarzeń")
        self.assertNotContains(r, "day-player.js")

    def test_anonymous_redirected(self):
        self.client.logout()
        r = self.client.get(reverse("scenario:run_play", args=[self.run.pk]))
        self.assertEqual(r.status_code, 302)
