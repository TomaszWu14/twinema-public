import hashlib
import json
from types import SimpleNamespace

from django import forms
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import any_role, designer
from render.models import RenderJob
from twin.blender_scene import model_floor, model_racks
from twin.design_kpi import compute_kpi, rack_to_element
from twin.models import WarehouseModel
from twin.shared import hall_feature_dict
from twin.views.warehouse_blender import _scene_from_request

from . import script_ai, youtube
from .api import END_S, TITLE_S
from .captions import build_srt, offsets, shot_cues
from .deck import build_deck
from .models import RENDER_RESOLUTION, MontageJob, Presentation, Shot
from .script import TARGET_WORDS, kpi_facts, template_script
from core import audit
from core.models import AuditEvent


def model_kpi(wm):
    """KPI modelu hali tym samym wzorem co wariant bazowy w porównaniu wariantów."""
    racks = model_racks(wm)
    if not racks:
        return {}
    floor = model_floor(wm, racks)
    features = [hall_feature_dict(f) for f in wm.features.all()]
    return compute_kpi([rack_to_element(r) for r in racks], features, floor["width"], floor["depth"])


def _replace_shots(p, shots):
    with transaction.atomic():
        p.shots.all().delete()
        Shot.objects.bulk_create(Shot(presentation=p, order=(i + 1) * 10, **s) for i, s in enumerate(shots))


class PresentationForm(forms.ModelForm):
    class Meta:
        model = Presentation
        fields = ["model", "title"]
        widgets = {"model": forms.Select(attrs={"class": "form-control"}),
                   "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 200})}


ShotFormSet = forms.modelformset_factory(
    Shot, fields=["order", "preset", "text"], extra=1, can_delete=True,
    widgets={"order": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 999}),
             "preset": forms.Select(attrs={"class": "form-control"}),
             "text": forms.Textarea(attrs={"class": "form-control", "rows": 3, "maxlength": 600})})


@any_role
def presentation_list(request):
    newest = WarehouseModel.objects.first()             # ordering: -created_at
    form = PresentationForm(initial={"model": newest.pk if newest else None})
    form.fields["model"].queryset = WarehouseModel.objects.all()
    return render(request, "studio/list.html", {
        "form": form,
        "presentations": Presentation.objects.select_related("model", "created_by").prefetch_related(
            "shots", Prefetch("montages", MontageJob.objects.filter(status="done"), to_attr="films"))[:50],
    })


@designer
@require_POST
def presentation_create(request):
    form = PresentationForm(request.POST)
    form.fields["model"].queryset = WarehouseModel.objects.all()
    if not form.is_valid():
        messages.error(request, "Wybierz model hali i wpisz tytuł filmu.")
        return redirect("studio:list")
    p = form.save(commit=False)
    p.created_by = request.user
    p.save()
    _replace_shots(p, template_script(model_kpi(p.model)))
    messages.success(request, f"Utworzono prezentację „{p}” ze szkicem tekstów z KPI modelu — popraw je "
                              "i zatwierdź przed renderem.")
    return redirect("studio:detail", pk=p.pk)


@any_role
def presentation_detail(request, pk):
    p = get_object_or_404(Presentation.objects.select_related("model"), pk=pk)
    formset = ShotFormSet(queryset=p.shots.all()) if p.is_draft else None
    shots = list(p.shots.select_related("render", "still"))
    n_words = sum(len(s.text.split()) for s in shots)
    montage = p.montages.first()
    jobs = [j for s in shots for j in (s.render, s.still) if j]
    return render(request, "studio/detail.html", {
        "p": p, "formset": formset, "shots": shots, "facts": kpi_facts(model_kpi(p.model)),
        "ai_enabled": script_ai.enabled(), "claude_model": settings.CLAUDE_MODEL,
        "film_seconds": round(sum(s.duration_s for s in shots)),
        "renders_done": sum(1 for s in shots if s.render_current and s.render.status == "done"),
        "stills_done": sum(1 for s in shots if s.still and s.still.status == "done" and s.still.preset == s.preset),
        "can_montage": montage_ready(shots), "montage": montage,
        "montage_current": bool(montage and montage_ready(shots) and montage.input_key == montage_input_key(p, shots)),
        "busy": any(j.status in ("queued", "running") for j in jobs)
        or bool(montage and montage.status in ("queued", "running")),
        "worker_enabled": bool(settings.RENDER_WORKER_TOKEN),
        "words": n_words, "target_words": TARGET_WORDS,
        "steps": Presentation.STATUS_CHOICES,
        "step_index": [k for k, _ in Presentation.STATUS_CHOICES].index(p.status),
    })


def _draft_or_back(request, p):
    if not p.is_draft:
        messages.error(request, "Tekst jest zatwierdzony — najpierw „Wróć do edycji”.")
        return False
    return True


@designer
@require_POST
def shots_save(request, pk):
    p = get_object_or_404(Presentation, pk=pk)
    if not _draft_or_back(request, p):
        return redirect("studio:detail", pk=pk)
    formset = ShotFormSet(request.POST, queryset=p.shots.all())
    if not formset.is_valid():
        for err in [e for f in formset.errors for e in f.values()] + list(formset.non_form_errors()):
            messages.error(request, " ".join(err))
        return redirect("studio:detail", pk=pk)
    for shot in formset.save(commit=False):
        shot.presentation = p
        shot.save()
    for shot in formset.deleted_objects:
        shot.delete()
    p.save(update_fields=["updated_at"])
    messages.success(request, "Zapisano teksty.")
    return redirect("studio:detail", pk=pk)


@designer
@require_POST
def shots_ai(request, pk):
    p = get_object_or_404(Presentation, pk=pk)
    if not _draft_or_back(request, p):
        return redirect("studio:detail", pk=pk)
    try:
        shots, warnings = script_ai.draft_script(kpi_facts(model_kpi(p.model)))
    except script_ai.ScriptAIError as exc:
        messages.error(request, str(exc))
        return redirect("studio:detail", pk=pk)
    if not shots:
        messages.error(request, "Szkic z AI nie zawierał żadnego poprawnego tekstu — obecne teksty bez zmian.")
        return redirect("studio:detail", pk=pk)
    _replace_shots(p, shots)
    messages.success(request, f"Claude napisał szkic: {len(shots)} ujęć. Przeczytaj, popraw i zatwierdź.")
    for w in warnings:
        messages.warning(request, w)
    return redirect("studio:detail", pk=pk)


@designer
@require_POST
def shots_template(request, pk):
    p = get_object_or_404(Presentation, pk=pk)
    if _draft_or_back(request, p):
        _replace_shots(p, template_script(model_kpi(p.model)))
        messages.success(request, "Wstawiono szkic z szablonu (KPI modelu).")
    return redirect("studio:detail", pk=pk)


@designer
@require_POST
def approve(request, pk):
    p = get_object_or_404(Presentation, pk=pk)
    if not _draft_or_back(request, p):
        return redirect("studio:detail", pk=pk)
    if not p.shots.exclude(text__regex=r"^\s*$").exists():
        messages.error(request, "Dodaj co najmniej jeden tekst ujęcia, zanim zatwierdzisz.")
        return redirect("studio:detail", pk=pk)
    p.shots.filter(text__regex=r"^\s*$").delete()
    p.status, p.approved_at = "approved", timezone.now()
    p.save(update_fields=["status", "approved_at", "updated_at"])
    messages.success(request, "Tekst zatwierdzony — można renderować ujęcia.")
    return redirect("studio:detail", pk=pk)


@designer
@require_POST
def reopen(request, pk):
    p = get_object_or_404(Presentation, pk=pk)
    p.status, p.approved_at = "draft", None
    p.save(update_fields=["status", "approved_at", "updated_at"])
    messages.success(request, "Tekst wrócił do edycji.")
    return redirect("studio:detail", pk=pk)


@designer
@require_POST
def presentation_delete(request, pk):
    p = get_object_or_404(Presentation, pk=pk)
    title = p.title
    audit.record(request, AuditEvent.DELETE, p, object_type="prezentacja filmowa", label=title)
    p.delete()
    messages.success(request, f"Usunięto prezentację „{title}”.")
    return redirect("studio:list")


@any_role
def subtitles(request, pk):
    """Napisy filmu z czasami jak w zmontowanym MP4 (przesunięte o planszę tytułową) — te same, które są
    wypalone w obrazie; na YouTube jako osobna ścieżka (tłumaczenie, wyszukiwanie)."""
    p = get_object_or_404(Presentation, pk=pk)
    shots = list(p.shots.all())
    if not shots:
        messages.error(request, "Dodaj teksty ujęć — napisy powstają z nich.")
        return redirect("studio:detail", pk=pk)
    resp = HttpResponse(film_srt(shots, start_s=TITLE_S), content_type="application/x-subrip; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="twinema_prezentacja_{p.pk}.srt"'
    return resp


@any_role
def youtube_text(request, pk):
    """Tytuł, opis i rozdziały filmu do wklejenia w YouTube Studio (oś czasu jak w montażu)."""
    from django.urls import reverse

    p = get_object_or_404(Presentation, pk=pk)
    shots = list(p.shots.all())
    if not shots:
        messages.error(request, "Dodaj teksty ujęć — opis z rozdziałami powstaje z nich.")
        return redirect("studio:detail", pk=pk)
    chapter_list = youtube.chapters(TITLE_S, [(s.duration_s, s.text) for s in shots], END_S)
    demo_url = request.build_absolute_uri(reverse("core:demo")) if settings.DEMO_PUBLIC else ""
    text = youtube.description(p.title, chapter_list, demo_url=demo_url, app_name=settings.APP_NAME)
    resp = HttpResponse(text, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="twinema_youtube_{p.pk}.txt"'
    return resp


def film_srt(shots, start_s=0.0):
    """SRT filmu; start_s = długość planszy tytułowej przy montażu."""
    starts = offsets([s.duration_s for s in shots], start_s=start_s)
    return build_srt([(t, shot_cues(s.text, s.duration_s)) for t, s in zip(starts, shots, strict=True)])


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


@designer
@require_POST
def render_shots(request, pk):
    """Dla każdego ujęcia klip MP4 (film) i kadr PNG (deck) z kolejki F3 — jednym kliknięciem, bo
    oba potrzebują tej samej sceny i kamery. Cache: scena + preset + długość/rodzaj + rozdzielczość →
    istniejące zlecenie (w kolejce, w toku albo gotowe) zamiast nowego."""
    p = get_object_or_404(Presentation.objects.select_related("model"), pk=pk)
    if p.status not in ("approved", "render", "montage", "done") or not p.shots.exists():
        messages.error(request, "Najpierw zatwierdź tekst.")
        return redirect("studio:detail", pk=pk)
    scene = _scene_from_request(SimpleNamespace(GET=QueryDict("")), p.model)
    created = reused = 0
    for n, shot in enumerate(p.shots.select_related("render", "still"), start=1):
        for field, kind, key in (("render", "video", _sha([scene, shot.preset, shot.render_seconds, RENDER_RESOLUTION])),
                                 ("still", "still", _sha([scene, shot.preset, "still", RENDER_RESOLUTION]))):
            current = getattr(shot, field)
            if getattr(shot, f"{field}_key") == key and current and current.status != "error":
                continue
            twin = (Shot.objects.filter(**{f"{field}_key": key, f"{field}__status__in": ("queued", "running", "done")})
                    .select_related(field).first())
            if twin:
                job, reused = getattr(twin, field), reused + 1
            else:
                job = RenderJob.objects.create(
                    model=p.model, preset=shot.preset, kind=kind, resolution=RENDER_RESOLUTION,
                    seconds=shot.render_seconds, created_by=request.user,
                    title=f"{p.title} — {'ujęcie' if kind == 'video' else 'kadr'} {n}"[:200])
                created += 1
            setattr(shot, field, job)
            setattr(shot, f"{field}_key", key)
            shot.save(update_fields=[field, f"{field}_key"])
    if p.status == "approved":
        p.status = "render"
        p.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Render ujęć i kadrów: {created} nowych zleceń w kolejce, {reused} z gotowych renderów."
                     if created or reused else "Wszystkie ujęcia mają aktualne klipy i kadry.")
    return redirect("studio:detail", pk=pk)


CAPTION_STYLE = 1        # zmiana wyglądu napisów w montażu → podbij, żeby stare filmy nie wróciły z cache


def montage_input_key(p, shots):
    """Wejście montażu: tytuł, klipy i teksty (napisy są w obrazie, więc poprawka tekstu = nowy film)."""
    return _sha([p.title, settings.APP_NAME, CAPTION_STYLE, [(s.render_id, s.text.strip()) for s in shots]])


def montage_ready(shots):
    return bool(shots) and all(s.render_current and s.render.status == "done" for s in shots)


@designer
@require_POST
def montage_create(request, pk):
    p = get_object_or_404(Presentation, pk=pk)
    shots = list(p.shots.select_related("render"))
    if not montage_ready(shots):
        messages.error(request, "Montaż ruszy, gdy wszystkie ujęcia mają gotowy, aktualny render.")
        return redirect("studio:detail", pk=pk)
    key = montage_input_key(p, shots)
    job = p.montages.filter(input_key=key, status__in=("queued", "running", "done")).first()
    if job is None:
        job = MontageJob.objects.create(presentation=p, input_key=key)
        messages.success(request, "Montaż w kolejce — worker z ffmpeg pobierze go przy następnym odpytaniu.")
    else:
        messages.info(request, "Ten film jest już zmontowany albo w trakcie — bez ponownego montażu.")
    p.status = "done" if job.status == "done" else "montage"
    p.save(update_fields=["status", "updated_at"])
    return redirect("studio:detail", pk=pk)


@any_role
def film_file(request, pk):
    job = get_object_or_404(MontageJob, pk=pk, status="done")
    if not job.result:
        raise Http404
    resp = FileResponse(job.result.open("rb"), content_type="video/mp4")
    disp = "attachment" if request.GET.get("pobierz") else "inline"
    resp["Content-Disposition"] = f'{disp}; filename="twinema_film_{job.presentation_id}.mp4"'
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


@any_role
def status_json(request, pk):
    """Stan renderów i montażu — strona odpytuje i przeładowuje się, gdy coś się zmieni."""
    p = get_object_or_404(Presentation, pk=pk)
    renders = list(p.shots.exclude(render=None).values_list("render__status", flat=True))
    stills = list(p.shots.exclude(still=None).values_list("still__status", flat=True))
    montage = p.montages.values_list("status", flat=True).first()
    jobs = renders + stills + [montage]
    return JsonResponse({"state": f"{p.status}|{','.join(renders)}|{','.join(stills)}|{montage or ''}",
                         "active": "queued" in jobs or "running" in jobs})


@any_role
def deck_pdf(request, pk):
    """Deck PDF: tytuł → liczby z KPI → ujęcie na stronę (kadr + tekst) → koniec.
    Brak gotowego kadru → miejsce zastępcze (deck da się pobrać na każdym etapie)."""
    p = get_object_or_404(Presentation.objects.select_related("model"), pk=pk)
    slides = []
    for s in p.shots.select_related("still"):
        image = None
        if s.still and s.still.status == "done" and s.still.preset == s.preset and s.still.result:
            with s.still.result.open("rb") as fh:
                image = fh.read()
        slides.append({"label": s.get_preset_display(), "text": s.text, "image": image})
    pdf = build_deck(p.title, settings.APP_NAME, timezone.localdate().strftime("%d.%m.%Y"),
                     kpi_facts(model_kpi(p.model)), slides)
    resp = HttpResponse(pdf, content_type="application/pdf")
    disp = "attachment" if request.GET.get("pobierz") else "inline"
    resp["Content-Disposition"] = f'{disp}; filename="twinema_deck_{p.pk}.pdf"'
    resp["X-Content-Type-Options"] = "nosniff"
    return resp
