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
# R-20: style tak samo — pliki CSS albo <style nonce=…>; atrybuty style= są blokowane (klasy z core/utilities.css,
# wartości z danych przez data-pct/data-color i ui.js). Zmiany przez el.style z JS (CSSOM) CSP nie blokuje.
# 'unsafe-eval' nie ma — three.js go nie potrzebuje; dodać świadomie, jeśli wejdzie biblioteka, która tak.
_CSP = (
    "default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'nonce-{nonce}'; "
    "font-src 'self'; img-src 'self' data: blob: https://portfolio.twapp.pl; media-src 'self' blob:; connect-src 'self'; "
    "frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'"
)
# Wyłączone funkcje przeglądarki, których aplikacja nie używa (fullscreen zostaje — fullscreen.js).
_PERMISSIONS_POLICY = "camera=(), geolocation=(), microphone=(), payment=(), usb=()"


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
    """Permissions-Policy + Content-Security-Policy (CSP_REPORT_ONLY=true → tylko raport) + `no-store` dla JSON.
    Pozostałe nagłówki (nosniff, Referrer-Policy, COOP, HSTS, X-Frame-Options) ustawia Django: SecurityMiddleware
    i XFrameOptionsMiddleware (twinema/settings.py)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)          # nowy na każde żądanie (US-005)
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        header = ("Content-Security-Policy-Report-Only" if getattr(settings, "CSP_REPORT_ONLY", False)
                  else "Content-Security-Policy")
        response.setdefault(header, _CSP.format(nonce=request.csp_nonce))
        if response.get("Content-Type", "").startswith("application/json"):
            response.setdefault("Cache-Control", "no-store")   # odpowiedzi API z danymi — bez zapisu w cache
        return response


def _is_internal(addr):
    """Adres zaufanego proxy: z TRUSTED_PROXIES, a gdy lista pusta — dowolny prywatny albo lokalny."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    nets = getattr(settings, "TRUSTED_PROXIES", [])
    if nets:
        return any(ip in ipaddress.ip_network(n, strict=False) for n in nets)
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


# US-017: ścieżki dostępne przed podaniem kodu TOTP (konfiguracja, weryfikacja, wylogowanie, pliki, zdrowie)
_TWO_FACTOR_EXEMPT = ("/2fa/", "/logout/", "/login/", "/static/", "/health/", "/favicon")


def two_factor_required(user):
    """TOTP wymagany: konto ma potwierdzone urządzenie albo jest Administratorem (Z-37, TWO_FACTOR_ADMIN)."""
    from django_otp import user_has_device

    from .validators import privileged
    if user_has_device(user, confirmed=True):
        return True
    return bool(getattr(settings, "TWO_FACTOR_ADMIN", True)) and privileged(user)


class TwoFactorMiddleware:
    """Zalogowany bez zweryfikowanego kodu, gdy kod jest wymagany → konfiguracja albo weryfikacja (US-017)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (user is not None and user.is_authenticated and not request.path.startswith(_TWO_FACTOR_EXEMPT)
                and not user.is_verified() and two_factor_required(user)):
            from django.shortcuts import redirect
            from django.utils.http import urlencode
            from django_otp import user_has_device
            target = "core:two_factor_verify" if user_has_device(user, confirmed=True) else "core:two_factor_setup"
            from django.urls import reverse
            return redirect(reverse(target) + "?" + urlencode({"next": request.get_full_path()}))
        return self.get_response(request)


# R-02 (przegląd SEC): ścieżki dostępne dla konta demo także wtedy, gdy na instancji są dane spoza demo
_DEMO_GUARD_EXEMPT = ("/demo/", "/logout/", "/login/", "/static/", "/health/", "/favicon", "/p/")


class DemoGuardMiddleware:
    """Konto `demo` (wejście gościa) traci sesję, gdy na instancji pojawią się dane spoza demo — sprawdzane przy
    każdym żądaniu konta demo (kilka zapytań EXISTS), nie tylko przy wejściu: sesja gościa trwa do 8 h."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .demo import DEMO_USER, exposure_reasons

        user = getattr(request, "user", None)
        if (user is not None and user.is_authenticated and user.get_username() == DEMO_USER
                and not request.path.startswith(_DEMO_GUARD_EXEMPT) and exposure_reasons()):
            from django.contrib.auth import logout
            from django.shortcuts import render
            logout(request)
            return render(request, "core/403.html", {"reason": "Wejście gościa jest wyłączone: na tej instancji są "
                                                                "dane spoza demo."}, status=403)
        return self.get_response(request)
