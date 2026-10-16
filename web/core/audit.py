"""Zapis do dziennika operacji wrażliwych (US-008).

Wywoływane z widoków po udanej operacji: `audit.record(request, AuditEvent.DELETE, obj)`.
Do dziennika nie trafiają dane źródłowe ani treść plików — tylko typ, identyfikator i nazwa obiektu.
"""

from .middleware import client_ip
from .models import AuditEvent


def record(request, action, obj=None, *, object_type="", object_id="", label="", detail=""):
    user = getattr(request, "user", None)
    actor = user if user is not None and user.is_authenticated else None
    if obj is not None:
        object_type = object_type or obj._meta.verbose_name
        object_id = object_id or str(obj.pk or "")
        label = label or str(obj)
    return AuditEvent.objects.create(
        actor=actor,
        actor_name=actor.get_username() if actor else "",
        action=action,
        object_type=str(object_type)[:60],
        object_id=str(object_id)[:40],
        object_label=str(label)[:200],
        detail=str(detail)[:300],
        ip=client_ip(request) or None,
    )
