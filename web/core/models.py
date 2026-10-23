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


class DemoObject(models.Model):
    """Obiekty utworzone przez `seed_demo` (R-02, przegląd SEC 2026-10-17): hala, scenariusz, prezentacja, import stanów.
    Wszystko spoza rejestru to dane spoza demo — blokują wejście gościa. Nazwa obiektu niczego nie przesądza."""

    content_type = models.ForeignKey("contenttypes.ContentType", on_delete=models.CASCADE)
    object_id = models.CharField(max_length=40)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["content_type", "object_id"], name="core_demo_object_unique")]

    def __str__(self):
        return f"demo {self.content_type.model} #{self.object_id}"


class DemoVisitor(models.Model):
    """Kto wszedł do publicznego demo (RODO CP-7): imię, nazwisko, firma — bez IP i user-agenta — oraz ile i jakie
    ekrany obejrzał (core/visitor_activity.py). Rekordy starsze niż RETENTION_DAYS usuwa `purge` (przy zapisie
    i z `audit_prune`)."""

    RETENTION_DAYS = 90
    MAX_SECTIONS = 20

    first_name = models.CharField("imię", max_length=100)
    last_name = models.CharField("nazwisko", max_length=100)
    company = models.CharField("firma", max_length=100)
    created_at = models.DateTimeField("data wejścia", auto_now_add=True)
    page_views = models.PositiveIntegerField("ekrany", default=0)
    last_seen_at = models.DateTimeField("ostatnia aktywność", null=True, blank=True)
    sections = models.JSONField("sekcje", default=dict, blank=True)   # sekcja → liczba ekranów, max MAX_SECTIONS

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "odwiedzający demo"
        verbose_name_plural = "odwiedzający demo"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.company})"

    def duration_minutes(self):
        """Czas wizyty = ostatnia aktywność − wejście, w pełnych minutach (None bez aktywności)."""
        if not self.last_seen_at:
            return None
        return max(0, int((self.last_seen_at - self.created_at).total_seconds() // 60))

    def top_sections(self, n=3):
        items = (self.sections or {}).items() if isinstance(self.sections, dict) else ()
        return [k for k, _ in sorted(items, key=lambda kv: (-kv[1], kv[0]))[:n]]

    @classmethod
    def purge(cls):
        from datetime import timedelta

        from django.utils import timezone
        return cls.objects.filter(created_at__lt=timezone.now() - timedelta(days=cls.RETENTION_DAYS)).delete()[0]
