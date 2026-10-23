"""Aktywność gościa demo po wejściu (RODO CP-7): ile ekranów, jak długo, jakie sekcje — bez IP i user-agenta.
Liczymy udane (2xx; przekierowanie liczy się dopiero na stronie docelowej) żądania GET stron HTML od gościa z ważnym ciasteczkiem bramki z id wpisu
(core/demo_gate.py). Pliki statyczne, /health/, API, panel admina i błędy nie liczą się. Każdy wyjątek →
ostrzeżenie w logach, odpowiedź bez zmian. Po `NTFY_ENGAGED_VIEWS` ekranach — jedno powiadomienie push."""
import logging
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import demo_gate, visitor_notify
from .models import DemoVisitor

SKIP_PREFIXES = ("/static/", "/media/", "/health/", "/api/", "/admin/", "/favicon", "/robots.txt")
MAX_SECTION_LEN = 40
_NOT_ALLOWED = re.compile(r"[^a-z0-9_-]")

log = logging.getLogger(__name__)


def section_of(path):
    """Pierwszy segment ścieżki (`/palety/123` → `palety`, `/` → `start`), tylko [a-z0-9_-], max 40 znaków."""
    first = path.strip("/").split("/", 1)[0]
    if not first:
        return "start"
    return _NOT_ALLOWED.sub("", first.lower())[:MAX_SECTION_LEN] or None


def countable(request, response):
    if request.method != "GET" or not 200 <= response.status_code < 300 or getattr(response, "streaming", False):
        return False
    if request.path.startswith(SKIP_PREFIXES) or "/api/" in request.path:
        return False
    return response.get("Content-Type", "").startswith("text/html")


def record(visitor_id, section):
    """+1 ekran, sekcja +1 (nowe ponad MAX_SECTIONS pomijamy), `last_seen_at`; próg → push. → nowa liczba albo None."""
    with transaction.atomic():
        v = (DemoVisitor.objects.select_for_update()
             .filter(pk=visitor_id).only("first_name", "last_name", "company", "page_views", "sections").first())
        if v is None:
            return None
        sections = v.sections if isinstance(v.sections, dict) else {}
        if section and (section in sections or len(sections) < DemoVisitor.MAX_SECTIONS):
            sections[section] = int(sections.get(section, 0)) + 1
        views = v.page_views + 1
        DemoVisitor.objects.filter(pk=visitor_id).update(page_views=views, last_seen_at=timezone.now(),
                                                         sections=sections)
    threshold = int(getattr(settings, "NTFY_ENGAGED_VIEWS", 10) or 0)
    if threshold and views == threshold:
        visitor_notify.notify_engaged({"first_name": v.first_name, "last_name": v.last_name,
                                       "company": v.company}, views)
    return views


class VisitorActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if countable(request, response):
                vid = demo_gate.visitor_id(request)
                if vid is not None:
                    record(vid, section_of(request.path))
        except Exception as exc:  # liczenie nigdy nie psuje odpowiedzi
            log.warning("Aktywność gościa demo nie zapisana: %s", exc.__class__.__name__)
        return response
