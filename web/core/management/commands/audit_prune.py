"""Retencja danych osobowych (NFR-014): wpisy dziennika operacji starsze niż AUDIT_RETENTION_DAYS (US-008, RODO CP-6)
i próby logowania django-axes starsze niż LOGIN_ATTEMPT_RETENTION_DAYS (RODO CP-2, decyzja PO: 30 dni).
Uruchamiane przy starcie kontenera; można też z harmonogramu."""

from datetime import timedelta

from axes.models import AccessAttempt, AccessFailureLog, AccessLog
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AuditEvent


class Command(BaseCommand):
    help = "Usuwa wpisy dziennika operacji i prób logowania starsze niż okres przechowywania."

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now - timedelta(days=settings.AUDIT_RETENTION_DAYS)
        deleted, _ = AuditEvent.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(f"Dziennik operacji: usunięto {deleted} wpisów starszych niż {settings.AUDIT_RETENTION_DAYS} dni.")
        login_cutoff = now - timedelta(days=settings.LOGIN_ATTEMPT_RETENTION_DAYS)
        n = sum(model.objects.filter(attempt_time__lt=login_cutoff).delete()[0]
                for model in (AccessAttempt, AccessFailureLog, AccessLog))
        self.stdout.write(f"Próby logowania: usunięto {n} wpisów starszych niż {settings.LOGIN_ATTEMPT_RETENTION_DAYS} dni.")
