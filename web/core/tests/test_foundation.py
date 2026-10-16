import os
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from core import roles
from twinema.config import load_env


class GroupContractTests(SimpleTestCase):
    """Stringi grup to wiersze auth_group — zmiana wartości = cichy odpływ uprawnień."""

    def test_group_names_are_frozen(self):
        self.assertEqual(roles.ALL_GROUPS, ["Administratorzy", "Projektant", "Podgląd"])


class ConfigTests(SimpleTestCase):
    def test_production_refuses_dev_secret(self):
        with mock.patch.dict(os.environ, {"DJANGO_DEBUG": "false"}, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                load_env()

    def test_production_boots_with_real_secret(self):
        with mock.patch.dict(os.environ, {"DJANGO_DEBUG": "false", "DJANGO_SECRET_KEY": "x" * 50}, clear=True):
            self.assertFalse(load_env().DJANGO_DEBUG)


class HealthTests(TestCase):
    def test_health_ok_with_version(self):
        r = self.client.get("/health/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["db"], "ok")
        self.assertIn("version", r.json())
        self.assertIn("X-Request-ID", r.headers)


class AccessTests(TestCase):
    def test_home_requires_login(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/login/"))

    def test_home_lists_modules_for_logged_user(self):
        self.client.force_login(User.objects.create_user("ania", password="x"))
        r = self.client.get("/")
        self.assertContains(r, "Prognozy i ML")

    def test_login_page_renders(self):
        self.assertContains(self.client.get("/login/"), "Zaloguj")

    def test_role_required_blocks_viewer(self):
        call_command("create_roles", stdout=open(os.devnull, "w"))
        user = User.objects.create_user("widz", password="x")
        user.groups.add(Group.objects.get(name=roles.GROUP_VIEWER))
        self.assertFalse(roles.has_role(user, roles.GROUP_DESIGNER))
        self.assertTrue(roles.has_role(user, roles.GROUP_VIEWER))


class ClientIpTests(SimpleTestCase):
    """US-006 (SEC): blokada logowania liczy adres klienta; X-Forwarded-For tylko od proxy w sieci wewnętrznej."""

    def _ip(self, remote, xff=None):
        from django.test import RequestFactory

        from core.middleware import client_ip
        extra = {"REMOTE_ADDR": remote} | ({"HTTP_X_FORWARDED_FOR": xff} if xff is not None else {})
        return client_ip(RequestFactory().get("/", **extra))

    def test_proxy_in_internal_network_last_xff_entry(self):
        self.assertEqual(self._ip("10.0.1.5", "198.51.100.7, 203.0.113.9"), "203.0.113.9")
        self.assertEqual(self._ip("172.18.0.2", "203.0.113.9"), "203.0.113.9")
        self.assertEqual(self._ip("127.0.0.1", "203.0.113.9"), "203.0.113.9")

    def test_direct_internet_connection_ignores_spoofed_xff(self):
        self.assertEqual(self._ip("8.8.8.8", "10.9.9.9"), "8.8.8.8")

    def test_without_header_uses_connection_address(self):
        self.assertEqual(self._ip("10.0.1.5"), "10.0.1.5")
        self.assertEqual(self._ip("1.1.1.1", ""), "1.1.1.1")
