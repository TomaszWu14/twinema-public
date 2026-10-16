"""Render ujęć z kolejki F3 (cache po hashu) i montaż przez API workera (token + jednorazowy claim)."""
import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from render.models import RenderJob
from studio.models import MontageJob, Presentation, Shot
from twin.models import WarehouseModel

TOKEN = "t" * 40
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
MEDIA = tempfile.mkdtemp(prefix="twinema_test_montage_")


LONG = " ".join(["słowo"] * 22)         # 22 / 2,2 + 1,5 = 11,5 s ujęcia


@override_settings(MEDIA_ROOT=MEDIA, RENDER_WORKER_TOKEN=TOKEN, APP_NAME="TWINEMA")
class RenderMontageTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.wm = WarehouseModel.objects.create(name="Hala", floor_width_m=30, floor_depth_m=20)
        self.wm.racks.create(zone="V", rack_id="001", n_bays=4, n_levels=3, x_m=4, y_m=4)
        self.user = User.objects.create_user("proj", password="x")
        self.user.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.client.force_login(self.user)
        self.p = Presentation.objects.create(model=self.wm, title="Film", status="approved")
        for i, (preset, text) in enumerate([("przelot", LONG), ("plan", "Druga.")]):
            Shot.objects.create(presentation=self.p, order=i, preset=preset, text=text)

    def _render(self):
        return self.client.post(reverse("studio:render_shots", args=[self.p.pk]))

    def _finish_renders(self):
        for job in RenderJob.objects.all():
            job.result.save(f"r{job.pk}.mp4", ContentFile(MP4), save=False)
            job.status = "done"
            job.save()

    def test_render_creates_jobs_with_text_length_and_status(self):
        self._render()
        jobs = list(RenderJob.objects.order_by("pk"))
        self.assertEqual([(j.preset, j.kind, j.resolution) for j in jobs],
                         [("przelot", "video", "1920x1080"), ("przelot", "still", "1920x1080"),
                          ("plan", "video", "1920x1080"), ("plan", "still", "1920x1080")])
        self.assertEqual([jobs[0].seconds, jobs[2].seconds], [12, 5])         # 11,5 s → 12; minimum 5 s
        self.assertEqual([jobs[0].title, jobs[1].title], ["Film — ujęcie 1", "Film — kadr 1"])
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, "render")

    def test_render_cache_same_scene_preset_length(self):
        self._render()
        self._render()                                        # drugi klik — nic nowego
        self.assertEqual(RenderJob.objects.count(), 4)        # 2 klipy + 2 kadry
        other = Presentation.objects.create(model=self.wm, title="Inny film", status="approved")
        s = self.p.shots.first()
        copy = Shot.objects.create(presentation=other, order=0, preset=s.preset, text=s.text)
        self.client.post(reverse("studio:render_shots", args=[other.pk]))
        copy.refresh_from_db()
        self.assertEqual((copy.render_id, copy.still_id), (s.render_id, s.still_id))   # z innej prezentacji
        self.assertEqual(RenderJob.objects.count(), 4)

    def test_preset_change_needs_new_render(self):
        self._render()
        Shot.objects.filter(preset="plan").update(preset="orbita")
        self._render()
        self.assertEqual(RenderJob.objects.count(), 6)        # nowy klip i nowy kadr tylko dla zmienionego

    def test_failed_still_is_rerendered_video_kept(self):
        self._render()
        s = self.p.shots.first()
        RenderJob.objects.filter(pk=s.still_id).update(status="error")
        self._render()
        s2 = Shot.objects.get(pk=s.pk)
        self.assertNotEqual(s2.still_id, s.still_id)
        self.assertEqual(s2.render_id, s.render_id)

    def test_render_blocked_in_draft(self):
        Presentation.objects.filter(pk=self.p.pk).update(status="draft")
        self._render()
        self.assertFalse(RenderJob.objects.exists())

    def test_longer_text_needs_new_clip_same_length_keeps_it(self):
        self._render()
        Shot.objects.filter(preset="plan").update(text="Inne krótkie.")          # nadal 5 s — klip zostaje
        self._render()
        self.assertEqual(RenderJob.objects.count(), 4)
        Shot.objects.filter(preset="plan").update(text=LONG)                       # 12 s — nowy klip
        self._render()
        self.assertEqual(RenderJob.objects.count(), 5)

    def test_viewer_cannot_render_or_montage(self):
        viewer = User.objects.create_user("zarzad", password="x")
        viewer.groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.client.force_login(viewer)
        self.assertEqual(self._render().status_code, 403)
        self.assertEqual(self.client.post(reverse("studio:montage_create", args=[self.p.pk])).status_code, 403)

    def test_montage_waits_for_renders_then_queues_once(self):
        self._render()
        self.client.post(reverse("studio:montage_create", args=[self.p.pk]))
        self.assertFalse(MontageJob.objects.exists())
        self._finish_renders()
        self.client.post(reverse("studio:montage_create", args=[self.p.pk]))
        self.client.post(reverse("studio:montage_create", args=[self.p.pk]))
        self.assertEqual(MontageJob.objects.count(), 1)
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, "montage")
        self.assertContains(self.client.get(reverse("studio:detail", args=[self.p.pk])), "Czeka na worker z ffmpeg")

    def _queued_montage(self):
        self._render()
        self._finish_renders()
        self.client.post(reverse("studio:montage_create", args=[self.p.pk]))
        return MontageJob.objects.get()

    def _api(self, name, *args, method="post", claim="", token=TOKEN, **data):
        return getattr(self.client, method)(reverse(name, args=args), data, HTTP_X_WORKER_TOKEN=token,
                                            HTTP_X_CLAIM=claim)

    def test_montage_gives_up_after_max_attempts(self):
        """US-015: montaż bez wyniku wraca do kolejki najwyżej 3 razy, potem kończy się błędem."""
        from datetime import timedelta

        from django.utils import timezone

        from render.api import MAX_ATTEMPTS
        job = self._queued_montage()
        for _ in range(MAX_ATTEMPTS):
            self.assertEqual(self._api("studio:api_claim").json()["id"], job.pk)
            MontageJob.objects.filter(pk=job.pk).update(claimed_at=timezone.now() - timedelta(hours=5))
        self.assertEqual(self._api("studio:api_claim").status_code, 204)
        job.refresh_from_db()
        self.assertEqual((job.status, job.attempts), ("error", MAX_ATTEMPTS))

    def test_worker_flow_manifest_files_result(self):
        job = self._queued_montage()
        self.assertEqual(self._api("studio:api_claim", token="zly" * 12).status_code, 403)
        man = self._api("studio:api_claim", worker="pc").json()
        self.assertEqual((man["id"], man["resolution"], man["title_s"]), (job.pk, "1920x1080", 3.0))
        self.assertEqual([s["duration"] for s in man["shots"]], [11.5, 5.0])
        self.assertEqual(man["shots"][1]["captions"], [[0.4, 4.4, "Druga."]])     # napisy na osi ujęcia
        self.assertEqual(" ".join(c[2].replace("\n", " ") for c in man["shots"][0]["captions"]), LONG)
        self.assertNotIn("audio_url", man["shots"][0])
        self.assertEqual(self._api("studio:api_claim").status_code, 204)        # jeden worker naraz
        claim = man["claim"]
        self.assertEqual(self._api("studio:api_clip", job.pk, 0, method="get", claim="inny").status_code, 403)
        clip = self._api("studio:api_clip", job.pk, 0, method="get", claim=claim)
        self.assertEqual(b"".join(clip.streaming_content), MP4)
        self.assertEqual(self._api("studio:api_clip", job.pk, 5, method="get", claim=claim).status_code, 404)
        bad = self._api("studio:api_result", job.pk, claim=claim, file=SimpleUploadedFile("f.mp4", b"nie-mp4" * 4))
        self.assertEqual(bad.status_code, 400)
        ok = self._api("studio:api_result", job.pk, claim=claim, file=SimpleUploadedFile("f.mp4", MP4), log="ok")
        self.assertEqual(ok.status_code, 200)
        job.refresh_from_db()
        self.p.refresh_from_db()
        self.assertEqual((job.status, self.p.status), ("done", "done"))
        page = self.client.get(reverse("studio:detail", args=[self.p.pk]))
        self.assertContains(page, reverse("studio:film_file", args=[job.pk]))
        self.assertEqual(self.client.get(reverse("studio:film_file", args=[job.pk]))["Content-Type"], "video/mp4")
        self.client.post(reverse("studio:montage_create", args=[self.p.pk]))   # ten sam materiał — cache
        self.assertEqual(MontageJob.objects.count(), 1)
        Shot.objects.filter(preset="plan").update(text="Poprawiony.")             # napis w obrazie — nowy montaż
        self.client.post(reverse("studio:montage_create", args=[self.p.pk]))
        self.assertEqual(MontageJob.objects.count(), 2)

    def test_worker_fail_shows_log_and_allows_retry(self):
        job = self._queued_montage()
        claim = self._api("studio:api_claim").json()["claim"]
        self._api("studio:api_fail", job.pk, claim=claim, error="ffmpeg: brak kodeka")
        page = self.client.get(reverse("studio:detail", args=[self.p.pk]))
        self.assertContains(page, "ffmpeg: brak kodeka")
        self.assertContains(page, "Zmontuj ponownie")
        self.client.post(reverse("studio:montage_create", args=[self.p.pk]))
        self.assertEqual(MontageJob.objects.filter(status="queued").count(), 1)

    def test_status_json(self):
        self._render()
        d = self.client.get(reverse("studio:status_json", args=[self.p.pk])).json()
        self.assertTrue(d["active"])
        self.assertEqual(d["state"], "render|queued,queued|queued,queued|")

    def test_subtitles_and_youtube_text_from_shot_texts(self):
        srt = self.client.get(reverse("studio:subtitles", args=[self.p.pk]))
        self.assertEqual(srt["Content-Type"], "application/x-subrip; charset=utf-8")
        body = srt.content.decode()
        self.assertTrue(body.startswith("1\n00:00:03,400 --> "))                  # plansza 3 s + wejście 0,4 s
        self.assertIn("00:00:14,900 --> 00:00:18,900\nDruga.", body)              # 3 + 11,5 + 0,4
        yt = self.client.get(reverse("studio:youtube", args=[self.p.pk]))
        self.assertEqual(yt["Content-Type"], "text/plain; charset=utf-8")
        self.assertTrue(yt.content.decode().startswith("Film\n"))
        Shot.objects.all().delete()
        self.assertRedirects(self.client.get(reverse("studio:subtitles", args=[self.p.pk])),
                             reverse("studio:detail", args=[self.p.pk]))

    def test_detail_without_voice_step(self):
        page = self.client.get(reverse("studio:detail", args=[self.p.pk]))
        self.assertNotContains(page, "Lektor")
        self.assertContains(page, "Renderuj ujęcia i kadry")
        self.assertContains(page, "ujęcie 11,5 s")
