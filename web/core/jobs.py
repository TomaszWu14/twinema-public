"""Kolejka zadań w bazie (US-007, US-024, ADR-0004).

`enqueue` dopisuje zadanie, proces `manage.py run_jobs` pobiera je po kolei (`run_next`). Pobranie to
warunkowy UPDATE (status queued → running), więc kilka procesów nie weźmie tego samego zadania.
Zadanie przerwane restartem wraca do kolejki; po MAX_ATTEMPTS próbach kończy się błędem.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.db.models import F
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import Job

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
KEEP_DONE = timedelta(days=7)
GAVE_UP = "Zadanie przerwano 3 razy (restart serwera?) — uruchom je ponownie."

# rodzaj zadania → funkcja(params) zwracająca wynik JSON (albo None); ścieżki, żeby worker nie ładował widoków
HANDLERS = {
    "twin.sim": "twin.jobs.simulate_day",
    "twin.calibration": "twin.jobs.calibrate_day",
    "twin.ewm_import": "twin.jobs.import_tasks",
    "scenario.sim": "scenario.jobs.simulate_scenario",
}


def enqueue(kind, params, *, key=None, user=None):
    """Nowe zadanie albo istniejące o tym samym kluczu; zadanie z błędem wraca do kolejki."""
    if kind not in HANDLERS:
        raise ValueError(f"Nieznany rodzaj zadania: {kind}")
    actor = user if user is not None and user.is_authenticated else None
    if key is None:
        return Job.objects.create(kind=kind, params=params, created_by=actor)
    job, created = Job.objects.get_or_create(key=key, defaults={"kind": kind, "params": params, "created_by": actor})
    if not created and job.status == Job.ERROR:
        Job.objects.filter(pk=job.pk, status=Job.ERROR).update(
            status=Job.QUEUED, attempts=0, message="", result=None, started_at=None, finished_at=None)
        job.refresh_from_db()
    return job


def requeue_stale(now=None):
    """Zadania „w toku” dłużej niż JOB_STALE_MIN: proces padł — do kolejki albo błąd po MAX_ATTEMPTS."""
    now = now or timezone.now()
    stale = Job.objects.filter(status=Job.RUNNING, started_at__lt=now - timedelta(minutes=settings.JOB_STALE_MIN))
    stale.filter(attempts__gte=MAX_ATTEMPTS).update(status=Job.ERROR, message=GAVE_UP, finished_at=now)
    stale.update(status=Job.QUEUED)


def claim():
    """Najstarsze zadanie z kolejki, oznaczone jako „w toku” — albo None."""
    for pk in Job.objects.filter(status=Job.QUEUED).values_list("pk", flat=True)[:10]:
        if Job.objects.filter(pk=pk, status=Job.QUEUED).update(
                status=Job.RUNNING, started_at=timezone.now(), attempts=F("attempts") + 1):
            return Job.objects.get(pk=pk)
    return None


def run_next():
    """Wykonuje jedno zadanie. True, gdy było co robić."""
    requeue_stale()
    job = claim()
    if job is None:
        return False
    try:
        result = import_string(HANDLERS[job.kind])(job.params)
    except Exception:                                    # granica zadania: błąd w zadaniu, nie w workerze
        log.exception("Zadanie %s przerwane", job)
        job.status, job.message = Job.ERROR, "Obliczenie przerwał błąd — szczegóły w logach serwera."
    else:
        job.status, job.result, job.message = Job.DONE, result, ""
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "result", "message", "finished_at"])
    return True


def run_pending(limit=100):
    """Wykonuje zadania z kolejki, aż się skończą (testy, uruchomienie jednorazowe)."""
    n = 0
    while n < limit and run_next():
        n += 1
    return n


def prune(now=None):
    """Usuwa zakończone zadania starsze niż KEEP_DONE — wyniki liczy się wtedy od nowa."""
    now = now or timezone.now()
    return Job.objects.filter(status__in=[Job.DONE, Job.ERROR], finished_at__lt=now - KEEP_DONE).delete()[0]


def worker_loop(poll_s=2.0, stop=lambda: False, sleep=None):
    import time
    sleep = sleep or time.sleep
    last_prune = None
    while not stop():
        close_old_connections()
        if last_prune is None or timezone.now() - last_prune > timedelta(hours=1):
            prune()
            last_prune = timezone.now()
        try:
            busy = run_next()
        except Exception:                                # np. chwilowy brak bazy — worker nie może paść
            log.exception("Błąd kolejki zadań")
            busy = False
        if not busy:
            sleep(poll_s)
