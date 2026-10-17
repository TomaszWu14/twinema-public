"""US-007, US-024: kolejka zadań w bazie — pobieranie, ponowienia po restarcie, błędy, retencja."""
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core import jobs
from core.models import Job

OK = "core.tests.test_jobs.ok_handler"
BOOM = "core.tests.test_jobs.failing_handler"


def ok_handler(params):
    return {"doubled": params["n"] * 2}


def failing_handler(params):
    raise RuntimeError("tajne szczegóły")


def _with(**handlers):
    return mock.patch.dict(jobs.HANDLERS, handlers)


class JobQueueTests(TestCase):
    def test_job_runs_and_stores_result(self):
        with _with(test=OK):
            job = jobs.enqueue("test", {"n": 21})
            self.assertEqual(job.status, Job.QUEUED)
            self.assertEqual(jobs.run_pending(), 1)
        job.refresh_from_db()
        self.assertEqual((job.status, job.result, job.attempts), (Job.DONE, {"doubled": 42}, 1))
        self.assertIsNotNone(job.finished_at)

    def test_same_key_reuses_job(self):
        with _with(test=OK):
            a = jobs.enqueue("test", {"n": 1}, key="k1")
            b = jobs.enqueue("test", {"n": 1}, key="k1")
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(Job.objects.count(), 1)

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            jobs.enqueue("nieznany", {})

    def test_failure_is_recorded_without_exception_details(self):
        with _with(test=BOOM), self.assertLogs("core.jobs", "ERROR"):
            job = jobs.enqueue("test", {}, key="k2")
            jobs.run_pending()
        job.refresh_from_db()
        self.assertEqual(job.status, Job.ERROR)
        self.assertNotIn("tajne", job.message)

    def test_failed_job_with_key_can_be_requeued(self):
        with _with(test=BOOM), self.assertLogs("core.jobs", "ERROR"):
            jobs.enqueue("test", {"n": 2}, key="k3")
            jobs.run_pending()
        with _with(test=OK):
            job = jobs.enqueue("test", {"n": 2}, key="k3")
            self.assertEqual(job.status, Job.QUEUED)
            jobs.run_pending()
        job.refresh_from_db()
        self.assertEqual(job.status, Job.DONE)

    def test_claim_takes_job_once(self):
        with _with(test=OK):
            jobs.enqueue("test", {"n": 1})
        first = jobs.claim()
        self.assertEqual(first.status, Job.RUNNING)
        self.assertIsNone(jobs.claim())

    @override_settings(JOB_STALE_MIN=60)
    def test_stale_running_job_is_requeued_then_gives_up(self):
        with _with(test=OK):
            job = jobs.enqueue("test", {"n": 1})
        old = timezone.now() - timedelta(minutes=61)
        Job.objects.filter(pk=job.pk).update(status=Job.RUNNING, attempts=1, started_at=old)
        jobs.requeue_stale()
        job.refresh_from_db()
        self.assertEqual(job.status, Job.QUEUED)
        Job.objects.filter(pk=job.pk).update(status=Job.RUNNING, attempts=jobs.MAX_ATTEMPTS, started_at=old)
        jobs.requeue_stale()
        job.refresh_from_db()
        self.assertEqual((job.status, job.message), (Job.ERROR, jobs.GAVE_UP))

    @override_settings(JOB_STALE_MIN=60)
    def test_long_job_with_live_heartbeat_stays_running(self):
        """Przegląd kodu (C): zadanie liczone dłużej niż JOB_STALE_MIN, ale z sygnałem workera, nie wraca do kolejki."""
        with _with(test=OK):
            job = jobs.enqueue("test", {"n": 1})
        now = timezone.now()
        Job.objects.filter(pk=job.pk).update(status=Job.RUNNING, attempts=1, started_at=now - timedelta(hours=3),
                                             heartbeat_at=now - timedelta(minutes=1))
        jobs.requeue_stale()
        job.refresh_from_db()
        self.assertEqual(job.status, Job.RUNNING)
        Job.objects.filter(pk=job.pk).update(heartbeat_at=now - timedelta(minutes=61))      # worker padł
        jobs.requeue_stale()
        job.refresh_from_db()
        self.assertEqual(job.status, Job.QUEUED)

    def test_result_of_a_taken_over_job_is_not_overwritten(self):
        """Wynik zapisuje tylko worker, który wciąż „ma” zadanie — inaczej nadpisałby stan innego workera."""
        def taken_over(params):
            Job.objects.filter(kind="test").update(status=Job.QUEUED)        # np. wróciło do kolejki
            return {"late": True}
        with _with(test=OK):
            job = jobs.enqueue("test", {"n": 1})
        with mock.patch.dict(jobs.HANDLERS, {"test": "core.tests.test_jobs.ok_handler"}), \
                mock.patch("core.tests.test_jobs.ok_handler", side_effect=taken_over):
            jobs.run_next()
        job.refresh_from_db()
        self.assertEqual((job.status, job.result), (Job.QUEUED, None))

    def test_heartbeat_marks_running_job(self):
        with _with(test=OK):
            job = jobs.enqueue("test", {"n": 1})
        job = jobs.claim()
        beat = jobs._Heartbeat(job)
        with mock.patch.object(beat.done, "wait", side_effect=[False, True]), mock.patch.object(jobs, "connection"):
            beat.run()                                                   # w wątku testu — bez własnego połączenia
        job.refresh_from_db()
        self.assertIsNotNone(job.heartbeat_at)

    def test_prune_removes_old_finished_jobs_only(self):
        with _with(test=OK):
            old = jobs.enqueue("test", {"n": 1})
            jobs.enqueue("test", {"n": 2})
            jobs.run_pending()
        Job.objects.filter(pk=old.pk).update(finished_at=timezone.now() - timedelta(days=8))
        queued = Job.objects.create(kind="test")
        self.assertEqual(jobs.prune(), 1)
        self.assertTrue(Job.objects.filter(pk=queued.pk).exists())

    def test_worker_loop_survives_errors_and_stops(self):
        calls = []
        # close_old_connections zamknąłby połączenie transakcji testu (PostgreSQL w CI) — w teście pętli wyłączone
        with mock.patch.object(jobs, "run_next", side_effect=[True, RuntimeError("baza"), False]), \
                mock.patch.object(jobs, "close_old_connections"), mock.patch.object(jobs, "prune"), \
                self.assertLogs("core.jobs", "ERROR"):
            jobs.worker_loop(stop=lambda: len(calls) >= 2, sleep=calls.append)
        self.assertEqual(calls, [2.0, 2.0])

    def test_run_jobs_once_command(self):
        with _with(test=OK):
            jobs.enqueue("test", {"n": 1})
            out = StringIO()
            call_command("run_jobs", "--once", stdout=out)
        self.assertIn("Wykonano zadań: 1", out.getvalue())


class JobStatusEndpointTests(TestCase):
    def test_status_for_logged_in_roles_without_result(self):
        from django.contrib.auth.models import Group, User
        from django.urls import reverse

        from core.roles import GROUP_VIEWER
        job = Job.objects.create(kind="twin.sim", params={"batch": 1}, status=Job.DONE, result={"x": 1})
        url = reverse("core:job_status", args=[job.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        u = User.objects.create_user("zarzad", password="x")
        u.groups.add(Group.objects.get_or_create(name=GROUP_VIEWER)[0])
        self.client.force_login(u)
        self.assertEqual(self.client.get(url).json(), {"status": "done", "status_display": "gotowe", "pending": False})
