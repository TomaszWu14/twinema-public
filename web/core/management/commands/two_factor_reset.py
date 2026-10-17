"""US-017: zgubiony telefon — usuwa urządzenia TOTP konta; przy następnym logowaniu konto skonfiguruje kod od nowa."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import AuditEvent


class Command(BaseCommand):
    help = "Zeruje weryfikację dwuetapową konta (urządzenia TOTP)."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **opts):
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"Nie ma konta „{username}”.")
        n, _ = TOTPDevice.objects.filter(user=user).delete()
        AuditEvent.objects.create(actor_name="manage.py", action=AuditEvent.TWO_FACTOR, object_type="konto",
                                  object_id=str(user.pk), object_label=username,
                                  detail="wyzerowano weryfikację dwuetapową")
        self.stdout.write(self.style.SUCCESS(f"Usunięto urządzeń: {n}. „{username}” skonfiguruje kod przy logowaniu."))
