"""Ekrany studia: role, szkic z szablonu, edycja tylko w szkicu, akceptacja, szkic z AI (mock)."""
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from studio.models import Presentation
from studio.script_ai import ScriptAIError
from twin.models import WarehouseModel
from core.jobs import run_pending


class StudioViewTests(TestCase):
    def setUp(self):
        self.wm = WarehouseModel.objects.create(name="Hala testowa", floor_width_m=40, floor_depth_m=30)
        self.wm.racks.create(zone="V", rack_id="001", n_bays=6, n_levels=4, x_m=4, y_m=4)
        self.designer = User.objects.create_user("proj", password="x")
        self.designer.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.viewer = User.objects.create_user("zarzad", password="x")
        self.viewer.groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.client.force_login(self.designer)

    def _create(self):
        self.client.post(reverse("studio:create"), {"model": self.wm.pk, "title": "Nowe centrum"})
        return Presentation.objects.get()

    def _formset(self, p, rows, extra=None):
        data = {"form-TOTAL_FORMS": len(rows) + (1 if extra else 0), "form-INITIAL_FORMS": len(rows),
                "form-MIN_NUM_FORMS": 0, "form-MAX_NUM_FORMS": 1000}
        for i, (shot, text, delete) in enumerate(rows):
            data.update({f"form-{i}-id": shot.pk, f"form-{i}-order": shot.order, f"form-{i}-preset": shot.preset,
                         f"form-{i}-text": text})
            if delete:
                data[f"form-{i}-DELETE"] = "on"
        if extra:
            n = len(rows)
            data.update({f"form-{n}-order": 99, f"form-{n}-preset": "orbita", f"form-{n}-text": extra})
        return self.client.post(reverse("studio:shots_save", args=[p.pk]), data)

    def test_create_seeds_template_shots_from_model_kpi(self):
        p = self._create()
        self.assertEqual((p.status, p.created_by), ("draft", self.designer))
        self.assertEqual(p.shots.count(), 5)
        self.assertIn("Miejsca paletowe", p.shots.get(preset="plan").text)
        r = self.client.get(reverse("studio:detail", args=[p.pk]))
        self.assertContains(r, "Zatwierdź tekst")
        self.assertContains(r, "Szkic z Claude wyłączony")      # brak klucza w testach

    def test_viewer_reads_but_cannot_change(self):
        p = self._create()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("studio:detail", args=[p.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("studio:list")).status_code, 200)
        self.assertEqual(self.client.post(reverse("studio:approve", args=[p.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("studio:create"), {"model": self.wm.pk, "title": "X"}).status_code, 403)

    def test_edit_add_delete_shots_in_draft(self):
        p = self._create()
        first, second, *_ = p.shots.all()
        self._formset(p, [(first, "Nowa kwestia otwarcia.", False), (second, second.text, True)],
                      extra="Dodatkowa kwestia.")
        texts = list(p.shots.values_list("text", flat=True))
        self.assertEqual(texts[0], "Nowa kwestia otwarcia.")
        self.assertNotIn(second.text, texts)
        self.assertEqual(texts[-1], "Dodatkowa kwestia.")

    def test_approve_locks_editing_until_reopen(self):
        p = self._create()
        self.client.post(reverse("studio:approve", args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, "approved")
        self.assertIsNotNone(p.approved_at)
        shot = p.shots.first()
        self._formset(p, [(shot, "Zmiana po akceptacji.", False)])
        self.assertNotEqual(p.shots.first().text, "Zmiana po akceptacji.")
        self.client.post(reverse("studio:shots_template", args=[p.pk]))
        self.assertEqual(p.shots.first().pk, shot.pk)              # szablon nie podmienił kwestii
        self.client.post(reverse("studio:reopen", args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual((p.status, p.approved_at), ("draft", None))

    def test_approve_requires_text(self):
        p = self._create()
        p.shots.update(text="  ")
        r = self.client.post(reverse("studio:approve", args=[p.pk]), follow=True)
        self.assertContains(r, "co najmniej jeden tekst ujęcia")
        p.refresh_from_db()
        self.assertEqual(p.status, "draft")

    def test_ai_without_key_shows_message_not_500(self):
        p = self._create()
        r = self.client.post(reverse("studio:shots_ai", args=[p.pk]), follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ANTHROPIC_API_KEY")
        self.assertEqual(p.shots.count(), 5)

    @override_settings(ANTHROPIC_API_KEY="sk-test")
    def test_ai_draft_replaces_shots_and_sends_only_facts(self):
        p = self._create()
        with mock.patch("studio.script_ai.draft_script",
                        return_value=([{"preset": "orbita", "text": "Orbita."}], ["Kwestia 2 była pusta."])) as m:
            self.client.post(reverse("studio:shots_ai", args=[p.pk]))
            self.assertEqual(p.shots.count(), 5)                           # T-1: szkic pisze worker kolejki
            run_pending()
        r = self.client.get(reverse("studio:detail", args=[p.pk]))
        facts = m.call_args.args[0]
        self.assertTrue(facts and not any("Hala testowa" in f for f in facts))   # bez nazwy modelu
        self.assertEqual(list(p.shots.values_list("preset", "text")), [("orbita", "Orbita.")])
        self.assertContains(r, "Kwestia 2 była pusta.")

    @override_settings(ANTHROPIC_API_KEY="sk-test")
    def test_ai_error_keeps_shots(self):
        p = self._create()
        with mock.patch("studio.script_ai.draft_script", side_effect=ScriptAIError("Limit zapytań do Claude")):
            self.client.post(reverse("studio:shots_ai", args=[p.pk]))
            run_pending()
        r = self.client.get(reverse("studio:detail", args=[p.pk]))
        self.assertContains(r, "Limit zapytań do Claude")
        self.assertEqual(p.shots.count(), 5)

    def test_delete(self):
        p = self._create()
        self.client.post(reverse("studio:delete", args=[p.pk]))
        self.assertFalse(Presentation.objects.exists())

    def test_hub_links_to_studio(self):
        self.assertContains(self.client.get(reverse("core:home")), reverse("studio:list"))
