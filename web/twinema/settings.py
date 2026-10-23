from pathlib import Path

from .config import load_env

BASE_DIR = Path(__file__).resolve().parent.parent  # web/

env = load_env()

SECRET_KEY = env.DJANGO_SECRET_KEY
DEBUG = env.DJANGO_DEBUG
APP_NAME = env.APP_NAME


def _csv(value):
    return [h.strip() for h in (value or "").split(",") if h.strip()]


ALLOWED_HOSTS = _csv(env.DJANGO_ALLOWED_HOSTS)
# HEALTHCHECK kontenera puka w 127.0.0.1 — bez tego 400 i Coolify cofa wdrożenie.
for _loopback in ("127.0.0.1", "localhost"):
    if _loopback not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_loopback)
CSRF_TRUSTED_ORIGINS = _csv(env.DJANGO_CSRF_TRUSTED_ORIGINS)

if not DEBUG:
    SECURE_SSL_REDIRECT = env.DJANGO_SSL_REDIRECT
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "core",
    "masterdata",
    "equipment",
    "twin",
    "render",
    "ml",
    "studio",
    "scenario",
]

MIDDLEWARE = [
    "core.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.middleware.TwoFactorMiddleware",
    "core.middleware.DemoGuardMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "twinema.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.branding",
                "core.context_processors.user_roles",
                "core.context_processors.navigation",
                "core.context_processors.csp",
            ],
        },
    },
]

WSGI_APPLICATION = "twinema.wsgi.application"


def _db_from_url(url):
    """DATABASE_URL (postgresql://USER:PASS@HOST:PORT/NAME?sslmode=…) → DATABASES['default'].
    None, gdy nieustawione — wtedy SQLite (lokalny dev bez Postgresa)."""
    url = (url or "").strip()
    if not url:
        return None
    import urllib.parse as _up
    u = _up.urlparse(url)
    query = dict(_up.parse_qsl(u.query))
    options = {}
    sslmode = query.get("sslmode") or env.DB_SSLMODE
    if sslmode:
        options["sslmode"] = sslmode
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _up.unquote(u.path.lstrip("/")),
        "USER": _up.unquote(u.username or ""),
        "PASSWORD": _up.unquote(u.password or ""),
        "HOST": u.hostname or "",
        "PORT": str(u.port or ""),
        "CONN_MAX_AGE": env.DB_CONN_MAX_AGE,
        "OPTIONS": options,
    }


DATABASES = {
    "default": _db_from_url(env.DATABASE_URL) or {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(env.DB_PATH or (BASE_DIR / "db.sqlite3")),
    }
}

LANGUAGE_CODE = "pl"
TIME_ZONE = "Europe/Warsaw"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = env.MEDIA_ROOT or str(BASE_DIR / "media")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Manifest (hashe + kompresja) tylko na prodzie — w dev/testach nie ma collectstatic.
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
                    else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "core.validators.PrivilegedPasswordLengthValidator"},     # US-017: ≥ 12 dla kont uprzywilejowanych
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_AGE = env.SESSION_COOKIE_AGE
SESSION_SAVE_EVERY_REQUEST = True
CSP_REPORT_ONLY = env.CSP_REPORT_ONLY

RENDER_WORKER_TOKEN = env.RENDER_WORKER_TOKEN
RENDER_MAX_MB = env.RENDER_MAX_MB
RENDER_STALE_MIN = env.RENDER_STALE_MIN
ANTHROPIC_API_KEY = env.ANTHROPIC_API_KEY
DEMO_PASSWORD = env.DEMO_PASSWORD
DEMO_PUBLIC = env.DEMO_PUBLIC
DEMO_VISITOR_GATE = env.DEMO_PUBLIC if env.DEMO_VISITOR_GATE is None else env.DEMO_VISITOR_GATE
DEMO_VIDEO_URL = env.DEMO_VIDEO_URL
AUDIT_RETENTION_DAYS = env.AUDIT_RETENTION_DAYS
LOGIN_ATTEMPT_RETENTION_DAYS = env.LOGIN_ATTEMPT_RETENTION_DAYS
JOB_STALE_MIN = env.JOB_STALE_MIN
BACKUP_DIR = env.BACKUP_DIR
# US-017 (decyzja PO Z-37): TOTP obowiązkowy dla Administratorów; testy wyłączają go runnerem (core.testing)
TWO_FACTOR_ADMIN = env.TWO_FACTOR_ADMIN
OTP_TOTP_ISSUER = APP_NAME
TEST_RUNNER = "core.testing.TestRunner"
CLAUDE_MODEL = env.CLAUDE_MODEL
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024     # formularze/importy; pliki renderów idą strumieniem
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

AXES_FAILURE_LIMIT = 5
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_CLIENT_IP_CALLABLE = None if DEBUG else "core.middleware.client_ip"
# US-006: od których adresów przyjmujemy X-Forwarded-For; puste = sieci prywatne (core.middleware.client_ip)
TRUSTED_PROXIES = [n.strip() for n in env.TRUSTED_PROXIES.split(",") if n.strip()]

GIT_SHA = (env.GIT_SHA or env.SOURCE_COMMIT or "unknown")[:40]   # /health/ i release Sentry

if env.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=env.SENTRY_DSN, environment=env.SENTRY_ENVIRONMENT,
                    traces_sample_rate=0.2, send_default_pii=False,
                    release=(GIT_SHA if GIT_SHA != "unknown" else None))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"verbose": {"format": "[{asctime}] {levelname} [{request_id}] {name}: {message}",
                               "style": "{"}},
    "filters": {"request_id": {"()": "core.middleware.RequestIDLogFilter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose",
                             "filters": ["request_id"]}},
    "root": {"handlers": ["console"], "level": env.DJANGO_LOG_LEVEL},
    "loggers": {"django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False}},
}
