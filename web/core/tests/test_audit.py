"""US-008: dziennik operacji wrażliwych — zapis, widok tylko dla Administratora, retencja."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import AuditEvent
from core.roles import GROUP_ADMIN, GROUP_DESIGNER, GROUP_VIEWER
from equipment.models import Equipment
from scenario.models import Scenario, Showcase
from twin.models import WarehouseModel


def _user(name, group):
    u = User.objects.create_user(name, password="x")
    u.groups.add(Group.objects.get_or_create(name=group)[0])
    return u


class AuditRecordTests(TestCase):
    def setUp(self):
        self.designer = _user("proj", GROUP_DESIGNER)
        self.client.force_login(self.designer)
        self.wm = WarehouseModel.objects.create(name="Hala A", floor_width_m=40, floor_depth_m=30)

    def test_hall_delete_is_recorded_but_confirmation_page_is_not(self):
        url = reverse("twin:warehouse_model_delete", args=[self.wm.pk])
        self.client.get(url)
        self.assertFalse(AuditEvent.objects.exists())
        self.client.post(url, REMOTE_ADDR="8.8.8.8")
        e = AuditEvent.objects.get()
        self.assertEqual((e.action, e.object_type, e.object_label, e.object_id),
                         (AuditEvent.DELETE, "hala", "Hala A", str(self.wm.pk)))
        self.assertEqual((e.actor, e.actor_name, e.ip), (self.designer, "proj", "8.8.8.8"))

    def test_scenario_and_equipment_delete_are_recorded(self):
        sc = Scenario.objects.create(name="Szczyt")
        eq = Equipment.objects.create(kind="reach", name="Mój reach", capacity_kg=1500, speed_loaded_kmh=10,
                                      speed_empty_kmh=11, created_by=self.designer)
        self.client.post(reverse("scenario:delete", args=[sc.pk]))
        self.client.post(reverse("equipment:delete", args=[eq.pk]))
        self.assertEqual(sorted(AuditEvent.objects.values_list("object_type", "object_label")),
                         [("model sprzętu", "Mój reach"), ("scenariusz", "Szczyt")])

    def test_public_link_create_and_revoke_are_recorded(self):
        show = Showcase.objects.create(title="Pokaz dla zarządu", model=self.wm)
        self.client.post(reverse("scenario:showcase_share", args=[show.pk]), {"days": 14})
        self.client.post(reverse("scenario:showcase_unshare", args=[show.pk]))
        self.client.post(reverse("scenario:showcase_unshare", args=[show.pk]))     # brak linku — bez wpisu
        events = list(AuditEvent.objects.order_by("id").values_list("action", "object_label", "detail"))
        self.assertEqual(events, [(AuditEvent.LINK_CREATE, "Pokaz dla zarządu", "ważny 14 dni"),
                                  (AuditEvent.LINK_REVOKE, "Pokaz dla zarządu", "")])
        self.assertNotIn(Showcase.objects.get().share_token or "-", str(events))   # token nie trafia do dziennika

    def test_masterdata_import_is_recorded_without_file_content(self):
        import tempfile
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="twinema-audit-")):
            self.client.post(reverse("masterdata:upload", args=["materials"]),
                             {"file": SimpleUploadedFile("m.csv", "Kod;Nazwa\nA1;Śruba\n".encode())})
        e = AuditEvent.objects.get()
        self.assertEqual((e.action, e.object_label), (AuditEvent.IMPORT, "m.csv"))
        self.assertIn("zlecony do kolejki", e.detail)
        self.assertNotIn("Śruba", f"{e.object_label} {e.detail}")

    def test_entry_survives_actor_account_deletion(self):
        self.client.post(reverse("twin:warehouse_model_delete", args=[self.wm.pk]))
        self.designer.delete()
        e = AuditEvent.objects.get()
        self.assertIsNone(e.actor)
        self.assertEqual(e.actor_name, "proj")


class AuditLogViewTests(TestCase):
    def setUp(self):
        self.admin = _user("admin1", GROUP_ADMIN)
        AuditEvent.objects.create(actor_name="proj", action=AuditEvent.DELETE, object_type="hala", object_label="Hala A")
        AuditEvent.objects.create(actor_name="proj", action=AuditEvent.IMPORT, object_type="import sprzętu",
                                  object_label="sprzet.xlsx")

    def test_only_admin_sees_log(self):
        url = reverse("core:audit_log")
        self.assertEqual(self.client.get(url).status_code, 302)
        for name, group in (("proj2", GROUP_DESIGNER), ("zarzad", GROUP_VIEWER)):
            self.client.force_login(_user(name, group))
            self.assertEqual(self.client.get(url).status_code, 403, name)
        self.client.force_login(self.admin)
        page = self.client.get(url)
        self.assertContains(page, "Hala A")
        self.assertContains(page, "sprzet.xlsx")

    def test_filter_by_action(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse("core:audit_log"), {"action": AuditEvent.IMPORT})
        self.assertContains(page, "sprzet.xlsx")
        self.assertNotContains(page, "Hala A")

    def test_module_tile_only_for_admin(self):
        url = reverse("core:audit_log")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("core:home")), f'href="{url}"')
        self.client.force_login(_user("proj3", GROUP_DESIGNER))
        self.assertNotContains(self.client.get(reverse("core:home")), f'href="{url}"')


class AuditPruneTests(TestCase):
    @override_settings(AUDIT_RETENTION_DAYS=365)
    def test_prune_removes_only_expired_entries(self):
        old = AuditEvent.objects.create(action=AuditEvent.DELETE, object_type="hala", object_label="stara")
        AuditEvent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=366))
        AuditEvent.objects.create(action=AuditEvent.DELETE, object_type="hala", object_label="nowa")
        call_command("audit_prune", stdout=StringIO())
        self.assertEqual(list(AuditEvent.objects.values_list("object_label", flat=True)), ["nowa"])


class LoginAttemptRetentionTests(TestCase):
    @override_settings(LOGIN_ATTEMPT_RETENTION_DAYS=30)
    def test_prune_removes_old_login_attempts(self):
        """NFR-014 / RODO CP-2 (decyzja PO): próby logowania starsze niż 30 dni są usuwane."""
        from axes.models import AccessAttempt, AccessLog
        for model, extra in ((AccessAttempt, {"failures_since_start": 1}), (AccessLog, {})):
            old = model.objects.create(username="x", ip_address="8.8.8.8", user_agent="t", **extra)
            model.objects.filter(pk=old.pk).update(attempt_time=timezone.now() - timedelta(days=31))
            model.objects.create(username="y", ip_address="8.8.8.8", user_agent="t", **extra)
        call_command("audit_prune", stdout=StringIO())
        self.assertEqual(list(AccessAttempt.objects.values_list("username", flat=True)), ["y"])
        self.assertEqual(list(AccessLog.objects.values_list("username", flat=True)), ["y"])
