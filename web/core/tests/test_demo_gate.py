"""Bramka odwiedzających demo (RODO CP-7): przedstawienie się przed wejściem, retencja 90 dni, lista tylko dla Admina."""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import DemoVisitor
from core.roles import GROUP_ADMIN, GROUP_VIEWER

OK = {"first_name": " Jan ", "last_name": "Kowalski", "company": "ACME", "gdpr": "1"}


@override_settings(DEMO_PUBLIC=True, DEMO_VISITOR_GATE=True)
class VisitorGateTests(TestCase):
    def setUp(self):
        self.demo = User.objects.create_user("demo")
        self.demo.groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.url = reverse("core:demo_enter")

    def _refused(self, r):
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(DemoVisitor.objects.count(), 0)

    def test_demo_page_shows_form_and_clause(self):
        r = self.client.get(reverse("core:demo"))
        self.assertContains(r, "przedstaw się, proszę.")
        self.assertContains(r, "art. 6 ust. 1 lit. f RODO")

    def test_without_data_refused(self):
        self._refused(self.client.post(self.url))

    def test_each_field_and_gdpr_required(self):
        for drop in OK:
            self._refused(self.client.post(self.url, {k: v for k, v in OK.items() if k != drop}))

    def test_invalid_values_refused(self):
        for bad in ("a", "x" * 101, "  ", "Jan\nKowalski", "Jan\x00"):
            self._refused(self.client.post(self.url, OK | {"company": bad}))

    def test_honeypot_refused(self):
        self._refused(self.client.post(self.url, OK | {"website": "http://spam"}))

    def test_valid_registers_and_logs_in_demo(self):
        r = self.client.post(self.url, OK)
        self.assertRedirects(r, reverse("core:home"))
        v = DemoVisitor.objects.get()
        self.assertEqual((v.first_name, v.last_name, v.company), ("Jan", "Kowalski", "ACME"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.demo.pk)
        c = r.cookies["demo_visitor"]
        self.assertEqual((c["max-age"], c["httponly"], c["samesite"]), (30 * 24 * 3600, True, "Lax"))

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_cookie_secure_in_production(self):
        self.assertTrue(self.client.post(self.url, OK).cookies["demo_visitor"]["secure"])

    def test_returning_visitor_not_asked_again(self):
        self.client.post(self.url, OK)
        self.client.post(reverse("core:logout"))
        self.assertNotContains(self.client.get(reverse("core:demo")), "przedstaw się")
        self.assertRedirects(self.client.post(self.url), reverse("core:home"))
        self.assertEqual(DemoVisitor.objects.count(), 1)

    def test_tampered_cookie_does_not_pass(self):
        self.client.cookies["demo_visitor"] = "1"
        self._refused(self.client.post(self.url))

    def test_login_health_and_static_not_blocked(self):
        self.assertEqual(self.client.get(reverse("core:login")).status_code, 200)
        self.assertEqual(self.client.get("/health/").status_code, 200)

    @override_settings(DEMO_VISITOR_GATE=False)
    def test_gate_off_enters_without_data(self):
        self.assertRedirects(self.client.post(self.url), reverse("core:home"))
        self.assertEqual(DemoVisitor.objects.count(), 0)


class RetentionAndAdminTests(TestCase):
    def _visitor(self, days, name="Ola"):
        v = DemoVisitor.objects.create(first_name=name, last_name="Nowak", company="Firma")
        DemoVisitor.objects.filter(pk=v.pk).update(created_at=timezone.now() - timedelta(days=days))
        return v

    def test_purge_deletes_older_than_90_days(self):
        old, fresh = self._visitor(91), self._visitor(89)
        self.assertEqual(DemoVisitor.purge(), 1)
        self.assertEqual(list(DemoVisitor.objects.all()), [fresh])
        self.assertFalse(DemoVisitor.objects.filter(pk=old.pk).exists())

    def test_purge_on_write_and_prune_command(self):
        from core import demo_gate
        self._visitor(100)
        demo_gate.register({"first_name": "Ewa", "last_name": "Lis", "company": "XY"})
        self.assertEqual(DemoVisitor.objects.count(), 1)
        self._visitor(120)
        call_command("audit_prune", stdout=__import__("io").StringIO())
        self.assertEqual(DemoVisitor.objects.count(), 1)

    def test_list_only_for_admin_newest_first(self):
        old, new = self._visitor(5, "Stary"), self._visitor(1, "Nowy")
        url = reverse("admin:core_demovisitor_changelist")
        admin = User.objects.create_user("adm", is_staff=True)
        admin.groups.add(Group.objects.create(name=GROUP_ADMIN))
        viewer = User.objects.create_user("pod", is_staff=True)
        viewer.groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.client.force_login(viewer)
        self.assertNotEqual(self.client.get(url).status_code, 200)
        self.client.force_login(admin)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(r.context["cl"].result_list), [new, old])
        self.assertEqual(self.client.get(reverse("admin:core_demovisitor_add")).status_code, 403)
