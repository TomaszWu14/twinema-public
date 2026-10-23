"""Bramka odwiedzających publiczne demo (RODO CP-7): grzeczne przedstawienie się przed wejściem.
Zapisujemy tylko imię, nazwisko i firmę — bez IP i user-agenta. Zgoda na wejście = podpisane ciasteczko na 30 dni
z identyfikatorem wpisu („v<id>”, do liczenia aktywności — core/visitor_activity.py). Starsze ciasteczka „1” (sprzed
zapisu id) nadal wpuszczają, ale aktywności nie liczymy."""
import re
import unicodedata

from django.conf import settings

from . import visitor_notify
from .models import DemoVisitor

COOKIE = "demo_visitor"
COOKIE_MAX_AGE = 30 * 24 * 3600
MIN_LEN, MAX_LEN = 2, 100
FIELDS = (("first_name", "Imię"), ("last_name", "Nazwisko"), ("company", "Firma"))


def gate_active():
    return bool(getattr(settings, "DEMO_VISITOR_GATE", False))


_VALUE = re.compile(r"v([1-9][0-9]{0,17})")


def _cookie(request):
    return request.get_signed_cookie(COOKIE, default=None, max_age=COOKIE_MAX_AGE)


def introduced(request):
    value = _cookie(request)
    return value == "1" or (value is not None and _VALUE.fullmatch(value) is not None)


def visitor_id(request):
    """Id wpisu `DemoVisitor` z ważnego podpisanego ciasteczka albo None (brak, podróbka, stary format „1”)."""
    m = _VALUE.fullmatch(_cookie(request) or "")
    return int(m.group(1)) if m else None


def clean_field(value):
    """Przycięty tekst 2–100 znaków bez znaków sterujących (także nowych linii) albo None."""
    value = (value or "").strip()
    if not MIN_LEN <= len(value) <= MAX_LEN or any(unicodedata.category(c).startswith("C") for c in value):
        return None
    return value


def validate(post):
    """→ (dane, błędy, bot). Wypełniona pułapka `website` = bot: odmowa bez szczegółów."""
    if post.get("website", ""):
        return {}, {}, True
    data, errors = {}, {}
    for name, label in FIELDS:
        value = clean_field(post.get(name))
        if value is None:
            errors[name] = f"{label}: wpisz od {MIN_LEN} do {MAX_LEN} znaków (bez znaków sterujących)."
        else:
            data[name] = value
    if not post.get("gdpr"):
        errors["gdpr"] = "Potwierdź, że zapoznałeś(-aś) się z informacją o danych osobowych."
    return data, errors, False


def register(data):
    DemoVisitor.purge()
    visitor = DemoVisitor.objects.create(**data)
    visitor_notify.notify(data)
    return visitor


def set_cookie(response, visitor):
    response.set_signed_cookie(COOKIE, f"v{visitor.pk}", max_age=COOKIE_MAX_AGE, httponly=True, samesite="Lax",
                               secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)))
