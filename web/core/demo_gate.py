"""Bramka odwiedzających publiczne demo (RODO CP-7): grzeczne przedstawienie się przed wejściem.
Zapisujemy tylko imię, nazwisko i firmę — bez IP i user-agenta. Zgoda na wejście = podpisane ciasteczko na 30 dni."""
import unicodedata

from django.conf import settings

from .models import DemoVisitor

COOKIE = "demo_visitor"
COOKIE_MAX_AGE = 30 * 24 * 3600
MIN_LEN, MAX_LEN = 2, 100
FIELDS = (("first_name", "Imię"), ("last_name", "Nazwisko"), ("company", "Firma"))


def gate_active():
    return bool(getattr(settings, "DEMO_VISITOR_GATE", False))


def introduced(request):
    return request.get_signed_cookie(COOKIE, default=None, max_age=COOKIE_MAX_AGE) == "1"


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
    return DemoVisitor.objects.create(**data)


def set_cookie(response):
    response.set_signed_cookie(COOKIE, "1", max_age=COOKIE_MAX_AGE, httponly=True, samesite="Lax",
                               secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)))
