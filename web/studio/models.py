"""Studio prezentacji: film o modelu hali składany z ujęć (preset kamery + tekst wypalony jako napis).

Statusy idą tylko do przodu: szkic → tekst zatwierdzony → render → montaż → gotowe.
Teksty wolno edytować wyłącznie w szkicu — nic nie idzie do renderu przed akceptacją.
Film nie ma lektora: długość ujęcia = czas na przeczytanie napisu (`captions.shot_seconds`).
"""
import math
import secrets

from django.conf import settings
from django.db import models

from render.models import RenderJob

from .captions import shot_seconds


class Presentation(models.Model):
    STATUS_CHOICES = [
        ("draft", "Szkic"),
        ("approved", "Tekst zatwierdzony"),
        ("render", "Render ujęć"),
        ("montage", "Montaż"),
        ("done", "Gotowe"),
    ]

    model = models.ForeignKey("twin.WarehouseModel", on_delete=models.CASCADE, related_name="presentations",
                              verbose_name="Model hali")
    title = models.CharField(max_length=200, verbose_name="Tytuł filmu")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="draft", db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        verbose_name = "Prezentacja"
        verbose_name_plural = "Prezentacje"

    def __str__(self):
        return self.title

    @property
    def is_draft(self):
        return self.status == "draft"

    @property
    def film_seconds(self):
        return round(sum(s.duration_s for s in self.shots.all()))


class Shot(models.Model):
    presentation = models.ForeignKey(Presentation, on_delete=models.CASCADE, related_name="shots")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="Kolejność")
    preset = models.CharField(max_length=12, choices=RenderJob.PRESET_CHOICES, default="ogolny",
                              verbose_name="Ujęcie")
    text = models.TextField(verbose_name="Tekst na ekranie")
    render = models.ForeignKey(RenderJob, on_delete=models.SET_NULL, null=True, blank=True, related_name="studio_shots")
    render_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    still = models.ForeignKey(RenderJob, on_delete=models.SET_NULL, null=True, blank=True, related_name="studio_stills")
    still_key = models.CharField(max_length=64, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "Ujęcie prezentacji"
        verbose_name_plural = "Ujęcia prezentacji"

    def __str__(self):
        return f"{self.order}. {self.get_preset_display()}"

    @property
    def duration_s(self):
        """Długość ujęcia w filmie: czas na przeczytanie napisu."""
        return shot_seconds(self.text)

    @property
    def render_seconds(self):
        """Długość klipu: pełne sekundy ≥ ujęcia, w granicach kolejki renderów (≤ 60 s)."""
        return min(60, math.ceil(self.duration_s))

    @property
    def render_current(self):
        """Render pasuje do obecnego presetu i długości ujęcia (stan zlecenia osobno)."""
        r = self.render
        return (r is not None and r.preset == self.preset and r.seconds == self.render_seconds
                and r.resolution == RENDER_RESOLUTION)


RENDER_RESOLUTION = "1920x1080"       # film dla zarządu — Full HD; podgląd ujęć i tak jest w kolejce F3


class MontageJob(models.Model):
    """Montaż filmu (ffmpeg w workerze na PC). Cache: ten sam `input_key` i gotowe → bez ponownego montażu."""
    STATUS_CHOICES = RenderJob.STATUS_CHOICES

    presentation = models.ForeignKey(Presentation, on_delete=models.CASCADE, related_name="montages")
    input_key = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="queued", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    worker = models.CharField(max_length=80, blank=True, default="")
    claim_token = models.CharField(max_length=64, blank=True, default="", editable=False)
    attempts = models.PositiveSmallIntegerField(default=0, editable=False)   # US-015
    result = models.FileField(upload_to="films/%Y/%m/", blank=True)
    log = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Montaż filmu"
        verbose_name_plural = "Montaże filmów"

    def __str__(self):
        return f"Montaż: {self.presentation}"

    def new_claim(self):
        self.claim_token = secrets.token_urlsafe(24)
        return self.claim_token
