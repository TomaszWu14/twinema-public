"""Usuwa wpisy dziennika operacji starsze niż AUDIT_RETENTION_DAYS (US-008, RODO CP-6)."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AuditEvent


class Command(BaseCommand):
    help = "Usuwa wpisy dziennika operacji starsze niż okres przechowywania."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
        deleted, _ = AuditEvent.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(f"Dziennik operacji: usunięto {deleted} wpisów starszych niż {settings.AUDIT_RETENTION_DAYS} dni.")
