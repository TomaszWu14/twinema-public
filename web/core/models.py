from django.conf import settings
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
    ACTIONS = [
        (DELETE, "Usunięcie"),
        (IMPORT, "Import pliku"),
        (LINK_CREATE, "Utworzenie linku publicznego"),
        (LINK_REVOKE, "Wyłączenie linku publicznego"),
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
