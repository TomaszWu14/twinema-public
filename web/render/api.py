"""API workera renderów. Uwierzytelnienie: nagłówek X-Worker-Token (RENDER_WORKER_TOKEN, ≥32 znaki)
+ dla operacji na zleceniu X-Claim (jednorazowy token przejęcia — spóźniony worker nie nadpisze wyniku).

  POST /api/render/claim/           → 200 zlecenie (JSON) albo 204, gdy kolejka pusta
  GET  /api/render/<id>/scene.json  → scena „twinema.scene”
  POST /api/render/<id>/result/     → multipart: file (PNG/MP4), log
  POST /api/render/<id>/fail/       → error (tekst)
"""
import hmac
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.core.files.base import File
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import RenderJob

SIGNATURES = {"png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"), "mp4": lambda b: b[4:8] == b"ftyp"}
LOG_MAX = 20_000


def _forbidden(msg="Brak dostępu workera."):
    return JsonResponse({"error": msg}, status=403)


def worker_required(view):
    def wrapped(request, *args, **kwargs):
        token = settings.RENDER_WORKER_TOKEN
        if not token:
            return _forbidden("API workera wyłączone — ustaw RENDER_WORKER_TOKEN.")
        if not hmac.compare_digest(token.encode(), request.headers.get("X-Worker-Token", "").encode()):
            return _forbidden()
        return view(request, *args, **kwargs)
    wrapped.__name__ = view.__name__
    return csrf_exempt(wrapped)


def _claimed_job(request, pk):
    job = get_object_or_404(RenderJob, pk=pk)
    claim = request.headers.get("X-Claim", "")
    if job.status != "running" or not job.claim_token or not hmac.compare_digest(
            job.claim_token.encode(), claim.encode()):
        return None
    return job


MAX_ATTEMPTS = 3          # US-015: tyle przejęć bez wyniku, potem błąd zamiast krążenia w kolejce bez końca
GAVE_UP = (f"Przerwano po {MAX_ATTEMPTS} próbach — stanowisko nie odesłało poprawnego wyniku "
           "(sprawdź log stanowiska, limit rozmiaru pliku i dostępność Blendera/ffmpeg).")


def requeue_stale(model=RenderJob):
    """Zlecenia „w toku” dłużej niż RENDER_STALE_MIN (worker padł albo serwer odrzucił wynik) wracają do kolejki;
    po MAX_ATTEMPTS przejęciach kończą się błędem. → liczba zleceń zwróconych do kolejki."""
    limit = timezone.now() - timedelta(minutes=settings.RENDER_STALE_MIN)
    stale = model.objects.filter(status="running", claimed_at__lt=limit)
    stale.filter(attempts__gte=MAX_ATTEMPTS).update(status="error", claim_token="", finished_at=timezone.now(),
                                                    log=GAVE_UP)
    return stale.filter(attempts__lt=MAX_ATTEMPTS).update(
        status="queued", claim_token="", log="Wróciło do kolejki: worker nie odesłał wyniku w czasie.")


@worker_required
@require_POST
def claim(request):
    requeue_stale()
    worker = (request.POST.get("worker") or request.headers.get("User-Agent", ""))[:80]
    for _ in range(5):                                   # kilku workerów naraz — wygrywa jeden
        job = RenderJob.objects.filter(status="queued").order_by("created_at", "pk").first()
        if job is None:
            return HttpResponse(status=204)
        token = job.new_claim()
        with transaction.atomic():
            won = RenderJob.objects.filter(pk=job.pk, status="queued").update(
                status="running", claim_token=token, claimed_at=timezone.now(), worker=worker,
                attempts=F("attempts") + 1)
        if won:
            return JsonResponse({
                "id": job.pk, "claim": token, "title": str(job), "preset": job.preset, "kind": job.kind,
                "ext": job.extension, "resolution": job.resolution, "seconds": job.seconds,
                "scene_url": request.build_absolute_uri(reverse("render:api_scene", args=[job.pk])),
                "result_url": request.build_absolute_uri(reverse("render:api_result", args=[job.pk])),
                "fail_url": request.build_absolute_uri(reverse("render:api_fail", args=[job.pk])),
            })
    return HttpResponse(status=204)


@worker_required
@require_GET
def scene(request, pk):
    from twin.views.warehouse_blender import _scene_from_request

    job = _claimed_job(request, pk)
    if job is None:
        return _forbidden("Zlecenie nie jest przejęte przez tego workera.")
    fake = SimpleNamespace(GET=QueryDict(job.scene_query))
    return JsonResponse(_scene_from_request(fake, job.model), json_dumps_params={"ensure_ascii": False})


@worker_required
@require_POST
def result(request, pk):
    job = _claimed_job(request, pk)
    if job is None:
        return _forbidden("Zlecenie nie jest przejęte przez tego workera.")
    f = request.FILES.get("file")
    if f is None:
        return JsonResponse({"error": "Brak pliku."}, status=400)
    if f.size > settings.RENDER_MAX_MB * 1024 * 1024:
        return JsonResponse({"error": f"Plik większy niż {settings.RENDER_MAX_MB} MB."}, status=413)
    head = f.read(16)
    f.seek(0)
    if not SIGNATURES[job.extension](head):
        return JsonResponse({"error": f"To nie jest plik {job.extension.upper()}."}, status=400)
    job.result.save(f"render_{job.pk}.{job.extension}", File(f), save=False)
    job.status, job.finished_at, job.claim_token = "done", timezone.now(), ""
    job.log = (request.POST.get("log") or "")[-LOG_MAX:]
    job.save()
    return JsonResponse({"ok": True, "id": job.pk})


@worker_required
@require_POST
def fail(request, pk):
    job = _claimed_job(request, pk)
    if job is None:
        return _forbidden("Zlecenie nie jest przejęte przez tego workera.")
    job.status, job.finished_at, job.claim_token = "error", timezone.now(), ""
    job.log = (request.POST.get("error") or "Błąd renderu bez opisu.")[-LOG_MAX:]
    job.save()
    return JsonResponse({"ok": True})
