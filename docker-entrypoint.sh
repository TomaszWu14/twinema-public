#!/bin/sh
set -e
cd /app/web

# Obraz startuje jako app (USER w Dockerfile). Gałąź root zostaje dla uruchomienia z `--user root`
# (np. jednorazowa naprawa uprawnień starego wolumenu): oddaje wolumeny app i schodzi do app przez gosu.
mkdir -p /app/web/media
if [ "$(id -u)" = "0" ]; then
    chown -R app:app /app/web/media 2>/dev/null || true
    if [ -n "$DB_PATH" ]; then chown -R app:app "$(dirname "$DB_PATH")" 2>/dev/null || true; fi
    RUN="gosu app"
else
    RUN=""
fi

echo "Migracje..."
$RUN python manage.py migrate --noinput
$RUN python manage.py create_roles
# Konto administratora z env (DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD) — tylko przy pierwszym starcie.
if [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    $RUN python manage.py createsuperuser --noinput 2>/dev/null || echo "Superuser już istnieje."
fi
# Publiczne demo: hala, scenariusz, stany i konto `demo` (Podgląd) — idempotentnie.
if [ "$DEMO_SEED" = "1" ] || [ "$DEMO_SEED" = "true" ]; then
    $RUN python manage.py seed_demo
fi

# Demo publiczne na instancji z danymi spoza demo = ich ujawnienie (R-02) — ostrzeżenie w logach.
$RUN python manage.py demo_exposure_check || true

exec $RUN gunicorn twinema.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --worker-class gthread --threads "${GUNICORN_THREADS:-4}" \
    --max-requests 1000 --max-requests-jitter 100 \
    --timeout 120 --graceful-timeout 30 \
    --access-logfile - --error-logfile -
