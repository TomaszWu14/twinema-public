"""Kolejka renderów: API workera (token, przejęcie, scena, wynik) i ekran zleceń."""
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from render.models import RenderJob
from twin.models import WarehouseModel

TOKEN = "t" * 40
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
# Osobny katalog na klasę: workery `--parallel` w CI (fork) dzielą ścieżki z importu modułu, więc
# rmtree jednej klasy kasował pliki drugiej uruchomionej równolegle w innym procesie.
MEDIA = tempfile.mkdtemp(prefix="twinema_test_media_")
MEDIA_SCREEN = tempfile.mkdtemp(prefix="twinema_test_media_screen_")


@override_settings(RENDER_WORKER_TOKEN=TOKEN, MEDIA_ROOT=MEDIA)
class WorkerApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.wm = WarehouseModel.objects.create(name="Hala", floor_width_m=30, floor_depth_m=20)
        self.wm.racks.create(zone="V", rack_id="001", n_bays=4, n_levels=3, x_m=4, y_m=4)
        self.job = RenderJob.objects.create(model=self.wm, preset="plan", kind="still", scene_query="pallets=0")

    def _claim(self, token=TOKEN):
        return self.client.post(reverse("render:api_claim"), {"worker": "pc-test"}, HTTP_X_WORKER_TOKEN=token)

    def _with_claim(self, url_name, claim, method="post", **data):
        call = getattr(self.client, method)
        return call(reverse(url_name, args=[self.job.pk]), data, HTTP_X_WORKER_TOKEN=TOKEN, HTTP_X_CLAIM=claim)

    def test_token_required_and_disabled_without_setting(self):
        self.assertEqual(self._claim("zly" * 12).status_code, 403)
        with override_settings(RENDER_WORKER_TOKEN=""):
            self.assertEqual(self._claim().status_code, 403)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "queued")

    def test_claim_once_then_empty_queue(self):
        r = self._claim()
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual((data["id"], data["preset"], data["ext"]), (self.job.pk, "plan", "png"))
        self.job.refresh_from_db()
        self.assertEqual((self.job.status, self.job.worker), ("running", "pc-test"))
        self.assertEqual(self._claim().status_code, 204)

    def test_scene_needs_matching_claim_and_uses_job_query(self):
        claim = self._claim().json()["claim"]
        self.assertEqual(self._with_claim("render:api_scene", "inny", method="get").status_code, 403)
        sc = self._with_claim("render:api_scene", claim, method="get").json()
        self.assertEqual(sc["format"], "twinema.scene")
        self.assertEqual(len(sc["racks"]), 1)
        self.assertEqual(sc["pallets"], [])                     # pallets=0 z parametrów zlecenia

    def test_result_validates_signature_and_finishes_job(self):
        claim = self._claim().json()["claim"]
        bad = self._with_claim("render:api_result", claim, file=SimpleUploadedFile("r.png", MP4))
        self.assertEqual(bad.status_code, 400)
        ok = self._with_claim("render:api_result", claim, file=SimpleUploadedFile("r.png", PNG), log="render 5 s")
        self.assertEqual(ok.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual((self.job.status, self.job.claim_token, self.job.log), ("done", "", "render 5 s"))
        self.assertTrue(self.job.result.name.endswith(f"render_{self.job.pk}.png"))
        # spóźniony worker z tym samym claim już nic nie nadpisze
        again = self._with_claim("render:api_result", claim, file=SimpleUploadedFile("r.png", PNG))
        self.assertEqual(again.status_code, 403)

    def test_fail_records_log(self):
        claim = self._claim().json()["claim"]
        self._with_claim("render:api_fail", claim, error="Traceback: brak pamięci GPU")
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "error")
        self.assertIn("brak pamięci GPU", self.job.log)

    def test_stale_running_job_returns_to_queue(self):
        self._claim()
        RenderJob.objects.filter(pk=self.job.pk).update(claimed_at=timezone.now() - timedelta(hours=5))
        r = self._claim()                                       # requeue przed przejęciem
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], self.job.pk)

    def test_job_gives_up_after_max_attempts(self):
        """US-015: zlecenie, które ciągle wraca bez wyniku (np. serwer odrzuca plik), po 3 próbach kończy się błędem."""
        from render.api import MAX_ATTEMPTS
        for attempt in range(1, MAX_ATTEMPTS + 1):
            r = self._claim()
            self.assertEqual((r.status_code, r.json()["id"]), (200, self.job.pk), attempt)
            self.job.refresh_from_db()
            self.assertEqual(self.job.attempts, attempt)
            RenderJob.objects.filter(pk=self.job.pk).update(claimed_at=timezone.now() - timedelta(hours=5))
        self.assertEqual(self._claim().status_code, 204)               # nie wraca do kolejki
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "error")
        self.assertIn("Przerwano po 3 próbach", self.job.log)

    def test_csrf_exempt_for_worker_only(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("render:api_claim"), {"worker": "x"}, HTTP_X_WORKER_TOKEN=TOKEN)
        self.assertEqual(r.status_code, 200)


@override_settings(MEDIA_ROOT=MEDIA_SCREEN, RENDER_WORKER_TOKEN="")
class RenderScreenTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_SCREEN, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.designer = User.objects.create_user("proj", password="x")
        cls.designer.groups.add(Group.objects.get_or_create(name=GROUP_DESIGNER)[0])
        cls.viewer = User.objects.create_user("widz", password="x")
        cls.viewer.groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])
        cls.wm = WarehouseModel.objects.create(name="Hala")

    def _create(self, **extra):
        data = {"model": self.wm.pk, "preset": "orbita", "kind": "video", "resolution": "1280x720",
                "seconds": 10, "source": "wt", "title": "Orbita demo", **extra}
        return self.client.post(reverse("render:create"), data)

    def test_designer_queues_job_with_built_scene_query(self):
        self.client.force_login(self.designer)
        self.assertRedirects(self._create(), reverse("render:jobs"))
        job = RenderJob.objects.get()
        self.assertEqual((job.preset, job.status, job.scene_query), ("orbita", "queued", "wt=latest&pallets=0"))
        r = self.client.get(reverse("render:jobs"))
        self.assertContains(r, "Orbita demo")
        self.assertContains(r, "API workera wyłączone")

    def test_viewer_cannot_queue_and_seconds_are_bounded(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self._create().status_code, 403)
        self.client.force_login(self.designer)
        self._create(seconds=600)
        self.assertFalse(RenderJob.objects.exists())

    def test_result_file_served_only_to_logged_users(self):
        job = RenderJob.objects.create(model=self.wm, kind="still", status="done")
        job.result.save("r.png", SimpleUploadedFile("r.png", PNG))
        url = reverse("render:result_file", args=[job.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.viewer)
        r = self.client.get(url)
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"))
        self.assertEqual(b"".join(r.streaming_content)[:8], PNG[:8])

    def test_model_view_links_render_and_status_json(self):
        self.client.force_login(self.viewer)
        r = self.client.get(reverse("twin:warehouse_model_view", args=[self.wm.pk]))
        self.assertContains(r, f"{reverse('render:jobs')}?model={self.wm.pk}")
        RenderJob.objects.create(model=self.wm)
        self.assertEqual(len(self.client.get(reverse("render:status_json")).json()["active"]), 1)
