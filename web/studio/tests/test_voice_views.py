"""Lektor w aplikacji: nagrywanie po akceptacji, cache po hashu, statusy, SRT. TTS zawsze mock."""
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.roles import GROUP_DESIGNER
from studio.models import Presentation, Shot, VoiceTrack
from studio.tts import TTSError
from twin.models import WarehouseModel

MEDIA = tempfile.mkdtemp(prefix="twinema_test_voice_")


def fake_tts(text, voice_id, model_id):
    n = len(text)
    return b"ID3fake-mp3", {"characters": list(text),
                            "character_start_times_seconds": [i * 0.05 for i in range(n)],
                            "character_end_times_seconds": [(i + 1) * 0.05 for i in range(n)]}


@override_settings(MEDIA_ROOT=MEDIA, ELEVENLABS_API_KEY="el-test", ELEVENLABS_VOICE_ID="glos-domyslny",
                   ELEVENLABS_MODEL="eleven_multilingual_v2")
class VoiceViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        wm = WarehouseModel.objects.create(name="Hala", floor_width_m=30, floor_depth_m=20)
        self.user = User.objects.create_user("proj", password="x")
        self.user.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.client.force_login(self.user)
        self.p = Presentation.objects.create(model=wm, title="Film", status="approved")
        self.s1 = Shot.objects.create(presentation=self.p, order=10, preset="przelot", text="Pierwsza kwestia.")
        self.s2 = Shot.objects.create(presentation=self.p, order=20, preset="plan", text="Druga kwestia.")

    def _voice(self, shot):
        return self.client.post(reverse("studio:voice_shot", args=[self.p.pk, shot.pk]))

    def test_blocked_before_approval(self):
        Presentation.objects.filter(pk=self.p.pk).update(status="draft")
        with mock.patch("studio.tts.synthesize", side_effect=fake_tts) as m:
            self.assertEqual(self._voice(self.s1).status_code, 409)
        m.assert_not_called()

    def test_record_all_moves_to_audio_and_srt_available(self):
        with mock.patch("studio.tts.synthesize", side_effect=fake_tts) as m:
            r1 = self._voice(self.s1).json()
            r2 = self._voice(self.s2).json()
        self.assertEqual((r1["cached"], r1["done"], r2["done"]), (False, False, True))
        self.assertEqual(r1["duration"], 0.85)
        self.assertEqual(m.call_args.args, ("Druga kwestia.", "glos-domyslny", "eleven_multilingual_v2"))
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, "audio")
        srt = self.client.get(reverse("studio:subtitles", args=[self.p.pk]))
        self.assertEqual(srt["Content-Type"], "application/x-subrip; charset=utf-8")
        body = srt.content.decode()
        self.assertIn("00:00:03,000 --> 00:00:03,850\nPierwsza kwestia.", body)   # po planszy tytułowej, jak w MP4
        self.assertIn("00:00:03,850 --> 00:00:04,550\nDruga kwestia.", body)   # przesunięta o 1. ujęcie
        yt = self.client.get(reverse("studio:youtube", args=[self.p.pk]))
        self.assertEqual(yt["Content-Type"], "text/plain; charset=utf-8")
        self.assertTrue(yt.content.decode().startswith("Film\n"))
        self.assertNotIn("Rozdziały", yt.content.decode())                    # 1,5 s narracji — za krótko na rozdziały
        self.s1.refresh_from_db()
        audio = self.client.get(reverse("studio:voice_file", args=[self.s1.voice_id]))
        self.assertEqual(audio["Content-Type"], "audio/mpeg")

    def test_cache_same_text_and_voice_no_second_call(self):
        Shot.objects.filter(pk=self.s2.pk).update(text="Pierwsza kwestia.")
        with mock.patch("studio.tts.synthesize", side_effect=fake_tts) as m:
            self._voice(self.s1)
            r = self._voice(self.s2).json()
        self.assertEqual(m.call_count, 1)
        self.assertTrue(r["cached"])
        self.assertEqual(VoiceTrack.objects.count(), 1)

    def test_text_change_invalidates_only_that_shot(self):
        with mock.patch("studio.tts.synthesize", side_effect=fake_tts):
            self._voice(self.s1)
            self._voice(self.s2)
        Shot.objects.filter(pk=self.s2.pk).update(text="Poprawiona druga kwestia.")
        self.p.status = "draft"
        self.p.save()
        self.client.post(reverse("studio:approve", args=[self.p.pk]))
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, "approved")              # jedna kwestia do ponownego nagrania
        shots = list(self.p.shots.select_related("voice"))
        self.assertEqual([s.voice_ok for s in shots], [True, False])
        page = self.client.get(reverse("studio:detail", args=[self.p.pk]))
        self.assertContains(page, "nagranie nieaktualne")
        self.assertContains(page, reverse("studio:voice_shot", args=[self.p.pk, self.s2.pk]))
        self.assertNotContains(page, reverse("studio:voice_shot", args=[self.p.pk, self.s1.pk]))

    def test_tts_error_is_json_message_and_nothing_saved(self):
        with mock.patch("studio.tts.synthesize", side_effect=TTSError("Limit ElevenLabs")):
            r = self._voice(self.s1)
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json(), {"error": "Limit ElevenLabs"})
        self.assertFalse(VoiceTrack.objects.exists())

    def test_disabled_without_key_shows_message(self):
        with override_settings(ELEVENLABS_API_KEY=""):
            page = self.client.get(reverse("studio:detail", args=[self.p.pk]))
        self.assertContains(page, "Lektor wyłączony")
        self.assertNotContains(page, "Nagraj lektora")

    def test_srt_before_recording_redirects_with_message(self):
        r = self.client.get(reverse("studio:subtitles", args=[self.p.pk]), follow=True)
        self.assertContains(r, "po nagraniu lektora")

    def test_presentation_voice_overrides_default(self):
        Presentation.objects.filter(pk=self.p.pk).update(voice_id="moj-glos")
        with mock.patch("studio.tts.synthesize", side_effect=fake_tts) as m:
            self._voice(self.s1)
        self.assertEqual(m.call_args.args[1], "moj-glos")
