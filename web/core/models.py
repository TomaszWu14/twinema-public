from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class AuditEvent(models.Model):
    """Dziennik operacji wrażliwych (US-008, R-08): kto, co, kiedy, na jakim obiekcie.

    Wpisy tylko dopisywane; usuwa je wyłącznie `audit_prune` po okresie przechowywania.
    Login aktora zapisany obok klucza — wpis zostaje czytelny po usunięciu konta (RODO CP-6).
    """

    DELETE = "delete"
    IMPORT = "import"
    LINK_CREATE = "link_create"
    LINK_REVOKE = "link_revoke"
    TWO_FACTOR = "two_factor"
    ACTIONS = [
        (DELETE, "Usunięcie"),
        (IMPORT, "Import pliku"),
        (LINK_CREATE, "Utworzenie linku publicznego"),
        (LINK_REVOKE, "Wyłączenie linku publicznego"),
        (TWO_FACTOR, "Weryfikacja dwuetapowa"),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    actor_name = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=20, choices=ACTIONS, db_index=True)
    object_type = models.CharField(max_length=60)
    object_id = models.CharField(max_length=40, blank=True)
    object_label = models.CharField(max_length=200, blank=True)
    detail = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_name} {self.action} {self.object_type} {self.object_label}"


class Job(models.Model):
    """Zadanie w kolejce w bazie (US-007, US-024, ADR-0004): długie obliczenia i importy poza żądaniem HTTP.

    Wykonuje je proces `manage.py run_jobs`. `key` = skrót parametrów obliczenia — ten sam zestaw
    danych i parametrów nie liczy się drugi raz, a wynik czyta każdy z dostępem do ekranu.
    """

    QUEUED, RUNNING, DONE, ERROR = "queued", "running", "done", "error"
    STATUSES = [(QUEUED, "w kolejce"), (RUNNING, "w toku"), (DONE, "gotowe"), (ERROR, "błąd")]

    kind = models.CharField(max_length=40)
    key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    params = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    status = models.CharField(max_length=10, choices=STATUSES, default=QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    result = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    message = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    # sygnał „żyję” workera co HEARTBEAT_S w trakcie obliczenia — do kolejki wraca tylko zadanie bez sygnału
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["kind", "status"])]

    def __str__(self):
        return f"{self.kind} #{self.pk} ({self.status})"

    @property
    def pending(self):
        return self.status in (self.QUEUED, self.RUNNING)
