"""Middleware przekrojowe: identyfikator żądania (korelacja logów) + nagłówki bezpieczeństwa."""
import contextvars
import ipaddress
import logging
import secrets
import uuid

from django.conf import settings

request_id_var = contextvars.ContextVar("request_id", default="-")


class RequestIDLogFilter(logging.Filter):
    """Dopisuje `record.request_id` z bieżącego żądania ("-" poza żądaniem)."""

    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


# US-005: skrypty tylko z serwera albo z jednorazowym nonce żądania (`csp_nonce` w szablonach) — bez
# 'unsafe-inline' dla skryptów; obsługa zdarzeń w atrybutach (onclick=) jest zablokowana (core/js/ui.js).
# Style zostają z 'unsafe-inline' (atrybuty style= w szablonach) — mniejsze ryzyko, dług T-17.
# 'unsafe-eval' nie ma — three.js go nie potrzebuje; dodać świadomie, jeśli wejdzie biblioteka, która tak.
_CSP = (
    "default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
    "frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'"
)
_PERMISSIONS_POLICY = "geolocation=(), microphone=(), payment=()"


class RequestIDMiddleware:
    """Bierze X-Request-ID od proxy albo nadaje nowy; odsyła go w odpowiedzi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = (request.headers.get("X-Request-ID") or uuid.uuid4().hex)[:64]
        request.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = rid
        return response


class SecurityHeadersMiddleware:
    """Permissions-Policy + Content-Security-Policy (domyślnie report-only)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)          # nowy na każde żądanie (US-005)
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        header = ("Content-Security-Policy-Report-Only" if getattr(settings, "CSP_REPORT_ONLY", False)
                  else "Content-Security-Policy")
        response.setdefault(header, _CSP.format(nonce=request.csp_nonce))
        return response


def _is_internal(addr):
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def client_ip(request):
    """IP klienta dla django-axes za jednym zaufanym proxy (Traefik/Coolify): ostatni wpis XFF.
    US-006: nagłówkowi wierzymy tylko, gdy żądanie przyszło z sieci wewnętrznej (proxy w sieci platformy).
    Połączenie wprost z internetu → adres połączenia, więc podmiana XFF nie omija blokady logowania."""
    remote = request.META.get("REMOTE_ADDR", "")
    if not _is_internal(remote):
        return remote
    last = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
    return last or remote
