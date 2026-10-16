# syntax=docker/dockerfile:1.7
# Kolejność: od najrzadziej zmienianego. SHA commita (SOURCE_COMMIT) ZAWSZE na końcu —
# Coolify podaje nowy przy każdym deployu, a ARG unieważnia cache wszystkiego po nim.
ARG PYTHON_IMAGE=python:3.13-slim

FROM ${PYTHON_IMAGE} AS builder
ENV PATH="/opt/venv/bin:$PATH" VIRTUAL_ENV=/opt/venv UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
# venv bez pip — instaluje uv; pip w obrazie produkcyjnym niepotrzebny (trivy: podatne biblioteki wbudowane w pip)
RUN python -m venv --without-pip /opt/venv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    uv pip install -r /tmp/requirements.txt

# Biblioteki JS (three.js, ECharts) — osobny etap zależny tylko od skryptu: CDN nie jest
# odpytywany przy każdej zmianie kodu.
FROM ${PYTHON_IMAGE} AS vendor
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates     && rm -rf /var/lib/apt/lists/*
WORKDIR /vendor/web
COPY web/scripts/fetch_vendor.sh scripts/fetch_vendor.sh
RUN sh scripts/fetch_vendor.sh

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gosu \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin app \
    && python -m pip uninstall --yes --quiet pip
COPY --from=builder /opt/venv /opt/venv
COPY --chmod=755 docker-entrypoint.sh ./
COPY web/ ./web/
COPY --from=vendor /vendor/web/twin/static/twin/vendor/ ./web/twin/static/twin/vendor/
WORKDIR /app/web
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=false DJANGO_ALLOWED_HOSTS=* \
    python manage.py collectstatic --noinput \
    && mkdir -p /app/web/media && chown app:app /app/web/media
# Kontener działa jako app od startu (US-014, trivy DS-0002). Nowy wolumen Docker przejmuje
# właściciela katalogu z obrazu; montowanie katalogu hosta wymaga chown 10001 (RUNBOOK).
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health/ || exit 1

ARG SOURCE_COMMIT=""
ENV GIT_SHA=${SOURCE_COMMIT}
ENTRYPOINT ["/app/docker-entrypoint.sh"]
