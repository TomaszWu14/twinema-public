"""R3 wydajność: GET scenariusza nie pisze do bazy, widoki animacji i prezentacji nie czytają listy zdarzeń
przebiegu (`events` — największa kolumna), flaga `has_events` zapisana przy symulacji."""
from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.roles import GROUP_DESIGNER
from scenario.models import Scenario, ScenarioRun, Showcase
from twin.models import WarehouseModel
from core.jobs import run_pending

EVENTS_COL = '"scenario_scenariorun"."events"'


class R3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("proj", password="x")
        cls.user.groups.add(Group.objects.create(name=GROUP_DESIGNER))

    def setUp(self):
        self.client.force_login(self.user)
        self.client.post(reverse("scenario:create"), {"name": "Rok bazowy"})
        self.sc = Scenario.objects.get()
        self.wm = WarehouseModel.objects.create(name="Hala", floor_width_m=80, floor_depth_m=50)
        for i in range(3):
            self.wm.features.create(kind="dock", label=f"Dok {i}", x_m=0, y_m=5 * i, width_m=3.5, depth_m=4)
        self.wm.racks.create(zone="V", rack_id="001", n_bays=6, n_levels=4, x_m=30, y_m=10)
        self.client.post(reverse("scenario:simulate", args=[self.sc.pk]),
                         {"model": self.wm.pk, "day": "typical", "runs": 2})
        run_pending()                                   # US-007: symulację liczy worker kolejki
        self.run = ScenarioRun.objects.get()

    def _sql(self, url):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(url).status_code, 200)
        return [q["sql"] for q in ctx.captured_queries]

    def test_simulation_stores_has_events(self):
        self.assertTrue(self.run.has_events)

    def test_scenario_detail_get_does_not_write(self):
        sql = self._sql(reverse("scenario:detail", args=[self.sc.pk]))
        writes = [q for q in sql if q.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                  and "django_session" not in q]                 # sesja = wyświetlone komunikaty, nie dane
        self.assertEqual(writes, [])

    def test_play_and_showcase_skip_events_column(self):
        self.assertFalse(any(EVENTS_COL in q for q in self._sql(reverse("scenario:run_play", args=[self.run.pk]))))
        show = Showcase.objects.create(title="P", model=self.wm, run=self.run, created_by=self.user)
        for name in ("scenario:showcase", "scenario:showcase_data"):
            sql = self._sql(reverse(name, args=[show.pk]))
            self.assertFalse(any(EVENTS_COL in q for q in sql), name)
        self.assertTrue(self.client.get(reverse("scenario:showcase_data", args=[show.pk])).json()["has_events"])
        self.assertTrue(any(EVENTS_COL in q for q in self._sql(reverse("scenario:run_events", args=[self.run.pk]))))

    def test_detail_query_count_is_flat(self):
        # strażnik N+1: drugi przebieg (dzień szczytowy) nie dokłada zapytań per wiersz
        url = reverse("scenario:detail", args=[self.sc.pk])
        n1 = len(self._sql(url))
        self.client.post(reverse("scenario:simulate", args=[self.sc.pk]),
                         {"model": self.wm.pk, "day": "peak", "runs": 2})
        run_pending()                                   # US-007: symulację liczy worker kolejki
        self.assertLessEqual(len(self._sql(url)), n1 + 3)
