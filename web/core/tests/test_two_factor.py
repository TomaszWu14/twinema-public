"""US-017 (decyzja PO Z-37): TOTP obowiązkowy dla Administratorów, opcjonalny dla pozostałych; hasła ≥ 12."""
from io import StringIO

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AuditEvent
from core.roles import GROUP_ADMIN, GROUP_DESIGNER


def _code(device):
    return f"{totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits):06d}"


@override_settings(TWO_FACTOR_ADMIN=True)
class TwoFactorTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin1", password="Bardzo-dlugie-haslo-1")
        self.admin.groups.add(Group.objects.get_or_create(name=GROUP_ADMIN)[0])
        self.designer = User.objects.create_user("proj", password="Haslo-projektanta")
        self.designer.groups.add(Group.objects.get_or_create(name=GROUP_DESIGNER)[0])

    def _login(self, user, password):
        return self.client.post(reverse("core:login"), {"username": user, "password": password})

    def test_admin_must_configure_then_reaches_app(self):
        self._login("admin1", "Bardzo-dlugie-haslo-1")
        r = self.client.get(reverse("core:audit_log"))
        self.assertRedirects(r, reverse("core:two_factor_setup") + "?next=%2Fdziennik%2F", fetch_redirect_response=False)
        page = self.client.get(reverse("core:two_factor_setup"))
        self.assertContains(page, "data:image/svg+xml")
        self.assertFalse(TOTPDevice.objects.exists())                    # klucz w sesji, nie w bazie
        device = TOTPDevice(key=self.client.session["two_factor_key"])
        bad = self.client.post(reverse("core:two_factor_setup"), {"token": "000000"})
        self.assertContains(bad, "Kod się nie zgadza")
        r = self.client.post(reverse("core:two_factor_setup"), {"token": _code(device), "next": "/dziennik/"})
        self.assertRedirects(r, reverse("core:audit_log"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("core:audit_log")).status_code, 200)
        self.assertTrue(TOTPDevice.objects.get(user=self.admin).confirmed)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.TWO_FACTOR).exists())

    def test_next_login_asks_for_code(self):
        device = TOTPDevice.objects.create(user=self.admin, name="t", confirmed=True)
        self._login("admin1", "Bardzo-dlugie-haslo-1")
        r = self.client.get(reverse("core:home"))
        self.assertRedirects(r, reverse("core:two_factor_verify") + "?next=%2F", fetch_redirect_response=False)
        self.assertContains(self.client.post(reverse("core:two_factor_verify"), {"token": "123456"}), "nie zgadza")
        device.refresh_from_db()
        device.throttle_reset()                                  # po błędzie django-otp wstrzymuje próby
        r = self.client.post(reverse("core:two_factor_verify"), {"token": _code(device), "next": "https://zly.example/"})
        self.assertRedirects(r, reverse("core:home"), fetch_redirect_response=False)   # bez przekierowania na obcy adres
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)

    def test_designer_without_device_is_not_asked_but_can_opt_in(self):
        self._login("proj", "Haslo-projektanta")
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)
        self.client.get(reverse("core:two_factor_setup"))
        device = TOTPDevice(key=self.client.session["two_factor_key"])
        self.client.post(reverse("core:two_factor_setup"), {"token": _code(device)})
        self.client.post(reverse("core:logout"))
        self._login("proj", "Haslo-projektanta")
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 302)          # włączony → kod przy logowaniu

    def test_demo_account_cannot_enable(self):
        demo = User.objects.create_user("demo")
        self.client.force_login(demo)
        self.assertEqual(self.client.get(reverse("core:two_factor_setup")).status_code, 403)
        self.assertFalse(TOTPDevice.objects.exists())

    def test_switch_off_only_with_setting(self):
        with override_settings(TWO_FACTOR_ADMIN=False):
            self.client.force_login(self.admin)
            self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)

    def test_reset_command(self):
        TOTPDevice.objects.create(user=self.admin, name="t", confirmed=True)
        call_command("two_factor_reset", "admin1", stdout=StringIO())
        self.assertFalse(TOTPDevice.objects.filter(user=self.admin).exists())
        self.assertEqual(AuditEvent.objects.get().detail, "wyzerowano weryfikację dwuetapową")


class PrivilegedPasswordTests(TestCase):
    def test_admin_needs_twelve_characters(self):
        admin = User.objects.create_user("adm")
        admin.groups.add(Group.objects.get_or_create(name=GROUP_ADMIN)[0])
        with self.assertRaises(ValidationError):
            validate_password("Krotkie-ha1", user=admin)              # 11 znaków
        validate_password("Dluzsze-haslo-1", user=admin)
        validate_password("Krotkie-ha1", user=User.objects.create_user("zwykly"))   # zwykłe konto: ≥ 10
        with self.assertRaises(ValidationError):
            validate_password("Krotkie-ha1", user=User(username="su", is_superuser=True))


@override_settings(TWO_FACTOR_ADMIN=True)
class TwoFactorSetupLimitTests(TestCase):
    def test_new_key_after_five_wrong_codes(self):
        admin = User.objects.create_user("admin2", password="x")
        admin.groups.add(Group.objects.get_or_create(name=GROUP_ADMIN)[0])
        self.client.force_login(admin)
        self.client.get(reverse("core:two_factor_setup"))
        first = self.client.session["two_factor_key"]
        for _ in range(6):
            self.client.post(reverse("core:two_factor_setup"), {"token": "000000"})
        self.client.get(reverse("core:two_factor_setup"))
        self.assertNotEqual(self.client.session["two_factor_key"], first)
        self.assertFalse(TOTPDevice.objects.exists())

    def test_sixth_wrong_code_shows_the_new_key_that_works(self):
        """Przegląd kodu (F): po wyczerpaniu prób strona pokazuje nowy klucz — kod z niego od razu działa."""
        admin = User.objects.create_user("admin3", password="x")
        admin.groups.add(Group.objects.get_or_create(name=GROUP_ADMIN)[0])
        self.client.force_login(admin)
        self.client.get(reverse("core:two_factor_setup"))
        for _ in range(6):
            page = self.client.post(reverse("core:two_factor_setup"), {"token": "000000"})
        self.assertContains(page, "wygenerowaliśmy nowy klucz")
        shown = page.context["secret"]
        device = TOTPDevice(key=self.client.session["two_factor_key"])
        import base64
        self.assertEqual(shown, base64.b32encode(device.bin_key).decode().rstrip("="))
        r = self.client.post(reverse("core:two_factor_setup"), {"token": _code(device)})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(TOTPDevice.objects.filter(user=admin).exists())


@override_settings(TWO_FACTOR_ADMIN=True)
class TwoFactorNextUrlTests(TestCase):
    def test_next_with_query_string_survives_setup_redirect(self):
        """Przegląd kodu (E): adres powrotu z kilkoma parametrami nie traci ich w drodze przez strony 2FA."""
        admin = User.objects.create_user("admin4", password="x")
        admin.groups.add(Group.objects.get_or_create(name=GROUP_ADMIN)[0])
        TOTPDevice.objects.create(user=admin, name="t", confirmed=True)
        self.client.force_login(admin)
        r = self.client.get(reverse("core:two_factor_setup"), {"next": "/scenariusze/?model=3&run=1"})
        self.assertRedirects(r, reverse("core:two_factor_verify") + "?next=%2Fscenariusze%2F%3Fmodel%3D3%26run%3D1",
                             fetch_redirect_response=False)
