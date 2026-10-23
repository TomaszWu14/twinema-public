"""Powiadomienie push (ntfy) o nowym odwiedzającym demo (RODO CP-7: odbiorca — usługa ntfy).
Bez `NTFY_URL` nic nie robi (zero ruchu sieciowego, tak też w testach). Wysyłka w wątku w tle:
gość nie czeka na ntfy, a każdy błąd kończy się ostrzeżeniem w logach."""
import logging
import threading
import urllib.request

from django.conf import settings

APP = "twinema"
TIMEOUT_S = 5
MAX_BODY = 300

log = logging.getLogger(__name__)


def build_request(visitor):
    """→ urllib.request.Request albo None, gdy powiadomienia są wyłączone."""
    url = getattr(settings, "NTFY_URL", "")
    if not url:
        return None
    if not url.startswith(("https://", "http://")):
        log.warning("NTFY_URL nie zaczyna się od https:// ani http:// — powiadomienie pominięte.")
        return None
    body = f"{visitor['first_name']} {visitor['last_name']} ({visitor['company']}) wszedł do {APP}"[:MAX_BODY]
    headers = {"Title": f"Nowy gosc: {APP}", "Tags": "bell", "Priority": "high",
               "Content-Type": "text/plain; charset=utf-8"}
    token = getattr(settings, "NTFY_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")


def send(req):
    try:
        # schemat http(s) sprawdza build_request (i walidacja NTFY_URL w twinema/config.py)
        with urllib.request.urlopen(req, timeout=TIMEOUT_S):  # nosec B310
            pass
    except Exception as exc:  # powiadomienie nigdy nie psuje wejścia gościa
        log.warning("Powiadomienie ntfy o odwiedzającym nie wysłane: %s", exc.__class__.__name__)


def notify(visitor):
    """Zleca powiadomienie o nowym odwiedzającym (dict: first_name, last_name, company)."""
    req = build_request(visitor)
    if req is not None:
        threading.Thread(target=send, args=(req,), name="ntfy-visitor", daemon=True).start()
