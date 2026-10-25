"""Typowana, walidowana konfiguracja z env (pydantic-settings).

`AppEnv()` jest tworzone RAZ na górze `settings.py`: brakująca albo zła zmienna wywala
start aplikacji z jednym zbiorczym komunikatem, a nie w środku żądania.
"""
from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-change-me"


class AppEnv(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    # ── Django ──────────────────────────────────────────────────────────────
    DJANGO_SECRET_KEY: str = DEV_SECRET
    DJANGO_DEBUG: bool = False
    DJANGO_ALLOWED_HOSTS: str = "127.0.0.1,localhost"
    DJANGO_CSRF_TRUSTED_ORIGINS: str = "http://localhost"
    DJANGO_SSL_REDIRECT: bool = False
    DJANGO_LOG_LEVEL: str = "INFO"
    APP_NAME: str = "TWINEMA"

    # ── Baza / pliki ────────────────────────────────────────────────────────
    DATABASE_URL: str = ""          # puste = SQLite (dev/CI bez Postgresa)
    DB_PATH: str = ""
    DB_SSLMODE: str = ""
    DB_CONN_MAX_AGE: int = 600
    MEDIA_ROOT: str = ""

    # ── Sesja / bezpieczeństwo ──────────────────────────────────────────────
    SESSION_COOKIE_AGE: int = 28800
    CSP_REPORT_ONLY: bool = False      # US-005: CSP wymuszana; true = tylko raport (awaryjny powrót)
    # US-006: sieci proxy, od których przyjmujemy X-Forwarded-For (CIDR po przecinku, np. sieć Traefika w Coolify).
    # Puste = każda sieć prywatna — bezpieczne tylko, gdy kontener nie publikuje portu wprost (bez proxy).
    TRUSTED_PROXIES: str = ""

    # ── Render (worker Blendera poza serwerem, pobiera zlecenia po HTTPS) ────
    RENDER_WORKER_TOKEN: str = ""      # puste = API workera wyłączone (403)
    RENDER_MAX_MB: int = 500           # limit pliku wyniku (PNG/MP4)
    RENDER_STALE_MIN: int = 120        # zlecenie „w toku” dłużej niż tyle minut wraca do kolejki

    # ── Studio prezentacji (do Claude idą wyłącznie zagregowane liczby) ─────
    ANTHROPIC_API_KEY: str = ""        # puste = szkic scenariusza z Claude wyłączony
    CLAUDE_MODEL: str = "claude-opus-5"

    # ── Publiczne demo (manage.py seed_demo) ────────────────────────────────
    DEMO_PASSWORD: str = ""            # hasło konta `demo` (rola Podgląd); puste = konto nie powstaje
    DEMO_SEED: bool = False            # True = docker-entrypoint.sh odpala seed_demo przy każdym starcie
    DEMO_PUBLIC: bool = False          # True = /demo/ wpuszcza bez hasła jako `demo` (Podgląd, tylko odczyt)
    DEMO_VISITOR_GATE: bool | None = None   # None = jak DEMO_PUBLIC: wejście do demo wymaga przedstawienia się (RODO CP-7)
    DEMO_VIDEO_URL: str = ""           # adres filmu (np. YouTube) na stronie /demo/; puste = bez przycisku
    PORTFOLIO_URL: str = "https://portfolio.twapp.pl"   # skąd demo sprawdza przepustkę gościa (GET /api/gosc); tylko https://
    PORTFOLIO_PASS: bool | None = None  # None = jak bramka dema; False = bez sprawdzania przepustki z portfolio
    NTFY_URL: str = ""                 # pełny adres tematu ntfy (push o nowym odwiedzającym); puste = wyłączone
    NTFY_TOKEN: str = ""               # opcjonalny token ntfy → nagłówek Authorization: Bearer
    NTFY_WATCH_COMPANIES: str = ""     # frazy po przecinku: firma gościa je zawiera → push pilny (tylko w env, nie w repo)
    NTFY_ENGAGED_VIEWS: int = 10       # po tylu ekranach gościa jeden push „ogląda demo”; 0 = wyłączone

    # ── Dziennik operacji wrażliwych (US-008) ──────────────────────────────
    # ── Drugi składnik logowania (US-017) ──────────────────────────────────────
    TWO_FACTOR_ADMIN: bool = True      # TOTP obowiązkowy dla Administratorów (Z-37); false tylko awaryjnie

    # ── Kopie zapasowe (US-009) ────────────────────────────────────────────────
    BACKUP_DIR: str = ""              # katalog kopii poza wolumenem mediów; puste = `manage.py backup` odmawia

    # ── Kolejka zadań w bazie (US-007, ADR-0004) ──────────────────────────────
    JOB_STALE_MIN: int = 60            # zadanie „w toku” dłużej = worker padł → wraca do kolejki
    RUN_WORKER: bool = True            # True = docker-entrypoint.sh uruchamia worker obok serwera
    AUDIT_RETENTION_DAYS: int = 365    # wpisy starsze usuwa `audit_prune` (przy starcie kontenera)
    LOGIN_ATTEMPT_RETENTION_DAYS: int = 30  # próby logowania (django-axes) — RODO CP-2, decyzja PO

    # ── Obserwowalność ──────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "production"
    GIT_SHA: str = ""                  # build-arg obrazu; puste → SOURCE_COMMIT (Coolify) → „unknown”
    SOURCE_COMMIT: str = ""

    @model_validator(mode="after")
    def _cross_field_checks(self) -> "AppEnv":
        if not self.DJANGO_DEBUG and self.DJANGO_SECRET_KEY == DEV_SECRET:
            raise ValueError("DJANGO_SECRET_KEY musi być ustawiony, gdy DJANGO_DEBUG=false.")
        if self.RENDER_WORKER_TOKEN and len(self.RENDER_WORKER_TOKEN) < 32:
            raise ValueError("RENDER_WORKER_TOKEN musi mieć co najmniej 32 znaki (np. secrets.token_urlsafe(32)).")
        if self.DEMO_PASSWORD and len(self.DEMO_PASSWORD) < 8:
            raise ValueError("DEMO_PASSWORD musi mieć co najmniej 8 znaków.")
        if self.DEMO_VIDEO_URL and not self.DEMO_VIDEO_URL.startswith("https://"):
            raise ValueError("DEMO_VIDEO_URL musi zaczynać się od https://.")
        if self.NTFY_URL and not self.NTFY_URL.startswith(("https://", "http://")):
            raise ValueError("NTFY_URL musi zaczynać się od https:// (albo http:// dla serwera w sieci lokalnej).")
        if self.NTFY_ENGAGED_VIEWS < 0:
            raise ValueError("NTFY_ENGAGED_VIEWS nie może być ujemne (0 = wyłączone).")
        if self.LOGIN_ATTEMPT_RETENTION_DAYS < 1:
            raise ValueError("LOGIN_ATTEMPT_RETENTION_DAYS musi wynosić co najmniej 1 dzień.")
        if self.TRUSTED_PROXIES:
            import ipaddress
            try:
                [ipaddress.ip_network(n.strip()) for n in self.TRUSTED_PROXIES.split(",") if n.strip()]
            except ValueError as exc:
                raise ValueError(f"TRUSTED_PROXIES: niepoprawna sieć ({exc}); podaj CIDR, np. 10.0.1.0/24.") from exc
        if self.AUDIT_RETENTION_DAYS < 30:
            raise ValueError("AUDIT_RETENTION_DAYS musi wynosić co najmniej 30 dni.")
        return self


def load_env() -> AppEnv:
    """Zwraca zwalidowany env; błąd → ImproperlyConfigured (czysty komunikat na starcie)."""
    try:
        return AppEnv()
    except Exception as exc:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(f"Błąd konfiguracji środowiska:\n{exc}") from exc
