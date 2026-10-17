"""ML1 prognoza + ML2 segmentacja: czyste moduły, zapis przebiegów, ekrany."""
import math
import random
from datetime import datetime, timedelta, timezone as dt_tz

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from ml import forecast, segmentation
from ml.models import ModelRun
from twin.models import WarehouseTask, WarehouseTaskBatch
from core.jobs import run_pending


class ForecastTests(SimpleTestCase):
    def test_holt_winters_beats_baseline_on_seasonal_series(self):
        forecast._demo()

    def test_hw_needs_two_seasons(self):
        self.assertNotIn("hw_add", forecast.candidates(60))
        self.assertIn("hw_add", forecast.candidates(2 * forecast.SEASON + forecast.BACKTEST))

    def test_baseline_always_ranked_and_growth_matches_trend(self):
        rng = random.Random(5)
        ys = [(t, 1000 * 1.004 ** t + rng.gauss(0, 15)) for t in range(60)]   # ~23 %/rok
        r = forecast.run(ys, years=2)
        self.assertTrue(r["ok"])
        self.assertIn("trend_log", [x["model"] for x in r["ranking"]])
        self.assertEqual(r["ranking"][0]["model"], r["chosen"])
        self.assertTrue(10 < r["growth_p50_pct"] < 40, r["growth_p50_pct"])
        self.assertGreaterEqual(r["growth_p90_pct"], r["growth_p50_pct"])
        self.assertEqual(len(r["forecast"]), 52)
        self.assertTrue(all(lo <= f <= up for lo, f, up in zip(r["lower"], r["forecast"], r["upper"], strict=True)))

    def test_too_short_history_is_reported_not_raised(self):
        r = forecast.run([(t, 100) for t in range(10)])
        self.assertFalse(r["ok"])
        self.assertIn("Za mało tygodni", r["reason"])

    def test_mape_ignores_zero_actuals(self):
        self.assertEqual(forecast.mape([0, 100], [5, 110]), 10.0)


class SegmentationTests(SimpleTestCase):
    def test_fast_and_slow_materials_split(self):
        segmentation._demo()

    def test_kmeans_deterministic(self):
        pts = [[math.sin(i), math.cos(i * 3)] for i in range(50)]
        self.assertEqual(segmentation.kmeans(pts, 3)[0], segmentation.kmeans(pts, 3)[0])

    def test_volume_used_only_when_known_for_all(self):
        days = list(range(20))
        md = {f"M{i}": {d: i % 5 + 1 for d in days} for i in range(30)}
        some = segmentation.segment(md, days, volumes={"M1": 12.0}, k=3)
        self.assertNotIn("volume", some["features"])
        allv = segmentation.segment(md, days, volumes={m: 10.0 + i for i, m in enumerate(md)}, k=3)
        self.assertIn("volume", allv["features"])

    def test_too_few_materials(self):
        r = segmentation.segment({"A": {1: 1}}, [1], k=4)
        self.assertFalse(r["ok"])


class MlRunTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.designer = User.objects.create_user("proj", password="x")
        cls.designer.groups.add(Group.objects.get_or_create(name=GROUP_DESIGNER)[0])
        cls.viewer = User.objects.create_user("widz", password="x")
        cls.viewer.groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])
        cls.batch = WarehouseTaskBatch.objects.create(name="Historia", status="done")
        rng = random.Random(1)
        start = datetime(2026, 1, 5, 8, tzinfo=dt_tz.utc)                    # poniedziałek
        tasks = []
        for day in range(20 * 7):
            when = start + timedelta(days=day)
            if when.weekday() >= 5:
                continue
            for i in range(30 + day // 7):
                mat = f"M{rng.choices(range(40), weights=[1 / (k + 1) for k in range(40)])[0]}"
                tasks.append(WarehouseTask(batch=cls.batch, kind="picking", material=mat, document=f"D{day}-{i // 3}",
                                           confirmed_at=when + timedelta(minutes=i)))
        WarehouseTask.objects.bulk_create(tasks)

    def test_viewer_cannot_run_designer_can_and_run_is_recorded(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(reverse("ml:run", args=["forecast"]), {"batch": self.batch.pk}).status_code, 403)
        self.client.force_login(self.designer)
        r = self.client.post(reverse("ml:run", args=["forecast"]), {"batch": self.batch.pk, "stream": "total", "years": 3})
        self.assertRedirects(r, reverse("ml:home"))                      # T-1: model liczy worker kolejki
        self.assertFalse(ModelRun.objects.exists())
        run_pending()
        run = ModelRun.objects.get()
        self.assertContains(self.client.get(reverse("ml:home")), reverse("ml:detail", args=[run.pk]))
        self.assertEqual((run.kind, run.version, run.params), ("forecast", forecast.VERSION, {"stream": "total", "years": 3}))
        self.assertTrue(run.result["ok"])
        self.assertIn("baseline_mape", run.metrics)
        page = self.client.get(reverse("ml:detail", args=[run.pk]))
        self.assertContains(page, "Test wsteczny")
        self.assertContains(page, "ml-data")

    def test_segmentation_run_and_csv(self):
        self.client.force_login(self.designer)
        self.client.post(reverse("ml:run", args=["segmentation"]), {"batch": self.batch.pk, "k": 3})
        run_pending()
        run = ModelRun.objects.get(kind="segmentation")
        self.assertTrue(run.result["ok"], run.result)
        self.assertEqual(len(run.result["segments"]), 3)
        self.assertContains(self.client.get(reverse("ml:detail", args=[run.pk])), "ABC×XYZ")
        csv = self.client.get(reverse("ml:segments_csv", args=[run.pk])).content.decode("utf-8")
        self.assertTrue(csv.startswith("﻿materiał;segment;nazwa segmentu"))
        self.assertIn("M0;0;", csv)                                           # najczęstszy → segment 1

    def test_home_lists_runs(self):
        self.client.force_login(self.viewer)
        self.assertContains(self.client.get(reverse("ml:home")), "Prognoza wolumenów")
