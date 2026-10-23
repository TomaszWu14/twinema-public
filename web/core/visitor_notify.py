"""Powiadomienie push (ntfy) o odwiedzającym demo (RODO CP-7: odbiorca — usługa ntfy).
Bez `NTFY_URL` nic nie robi (zero ruchu sieciowego, tak też w testach). Wysyłka w wątku w tle:
gość nie czeka na ntfy, a każdy błąd kończy się ostrzeżeniem w logach.
Dwa rodzaje: nowy gość (`notify`) i gość zaangażowany — `NTFY_ENGAGED_VIEWS` ekranów (`notify_engaged`).
Firma z listy `NTFY_WATCH_COMPANIES` (frazy tylko w env) → priorytet pilny."""
import logging
import threading
import unicodedata
import urllib.request

from django.conf import settings

APP = "twinema"
TIMEOUT_S = 5
MAX_BODY = 300
MIN_PHRASE = 2

log = logging.getLogger(__name__)


def normalize(text):
    """Bez wielkości liter, polskich znaków (NFKD; „ł” nie ma rozkładu — zamiana ręczna) i nadmiarowych spacji."""
    text = unicodedata.normalize("NFKD", (text or "").casefold().replace("ł", "l"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def watch_phrases():
    raw = getattr(settings, "NTFY_WATCH_COMPANIES", "")
    items = raw.split(",") if isinstance(raw, str) else raw
    return [p for p in (normalize(x) for x in items) if len(p) >= MIN_PHRASE]


def watched(company):
    """Firma gościa zawiera którąś z fraz `NTFY_WATCH_COMPANIES` (po normalizacji)."""
    name = normalize(company)
    return any(p in name for p in watch_phrases())


def _request(title, tags, priority, body):
    url = getattr(settings, "NTFY_URL", "")
    if not url:
        return None
    if not url.startswith(("https://", "http://")):
        log.warning("NTFY_URL nie zaczyna się od https:// ani http:// — powiadomienie pominięte.")
        return None
    headers = {"Title": title, "Tags": tags, "Priority": priority, "Content-Type": "text/plain; charset=utf-8"}
    token = getattr(settings, "NTFY_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, data=body[:MAX_BODY].encode("utf-8"), headers=headers, method="POST")


def _who(visitor):
    return f"{visitor['first_name']} {visitor['last_name']} ({visitor['company']})"


def build_request(visitor):
    """Nowy gość → urllib.request.Request albo None, gdy powiadomienia są wyłączone."""
    body = f"{_who(visitor)} wszedł do {APP}"
    if watched(visitor["company"]):
        return _request(f"UWAGA firma z listy: {APP}", "rotating_light", "urgent", "⚠️ " + body)
    return _request(f"Nowy gosc: {APP}", "bell", "high", body)


def build_engaged_request(visitor, views):
    """Gość obejrzał `views` ekranów → Request albo None."""
    priority = "urgent" if watched(visitor["company"]) else "default"
    return _request(f"Gosc oglada demo: {APP}", "eyes", priority,
                    f"{_who(visitor)} obejrzał już {views} ekranów w {APP}")


def send(req):
    try:
        # schemat http(s) sprawdza _request (i walidacja NTFY_URL w twinema/config.py)
        with urllib.request.urlopen(req, timeout=TIMEOUT_S):  # nosec B310
            pass
    except Exception as exc:  # powiadomienie nigdy nie psuje wejścia gościa
        log.warning("Powiadomienie ntfy o odwiedzającym nie wysłane: %s", exc.__class__.__name__)


def _dispatch(req):
    if req is not None:
        threading.Thread(target=send, args=(req,), name="ntfy-visitor", daemon=True).start()


def notify(visitor):
    """Zleca powiadomienie o nowym odwiedzającym (dict: first_name, last_name, company)."""
    _dispatch(build_request(visitor))


def notify_engaged(visitor, views):
    """Zleca jedno powiadomienie „gość ogląda demo” (dict jak w `notify`)."""
    _dispatch(build_engaged_request(visitor, views))
