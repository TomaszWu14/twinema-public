"""Zlecenia renderu: aplikacja kolejkuje, worker z Blenderem (poza serwerem) pobiera, renderuje
i odsyła plik. Scena = ta sama, którą widzi odtwarzacz 3D (parametry zapytania w `scene_query`)."""
import secrets

from django.conf import settings
from django.db import models


class RenderJob(models.Model):
    PRESET_CHOICES = [
        ("przelot", "Przelot nad halą"),
        ("orbita", "Orbita wokół hali"),
        ("przejazd", "Przejazd wzdłuż hali (nisko)"),
        ("plan", "Plan z góry"),
        ("ogolny", "Widok ogólny (statyczny)"),
    ]
    KIND_CHOICES = [("video", "Klip MP4"), ("still", "Kadr PNG")]
    STATUS_CHOICES = [("queued", "W kolejce"), ("running", "Renderuje się"), ("done", "Gotowe"),
                      ("error", "Błąd")]
    RES_CHOICES = [("1280x720", "HD 1280×720"), ("1920x1080", "Full HD 1920×1080"), ("640x360", "Podgląd 640×360")]

    model = models.ForeignKey("twin.WarehouseModel", on_delete=models.CASCADE, related_name="render_jobs",
                              verbose_name="Model hali")
    preset = models.CharField(max_length=12, choices=PRESET_CHOICES, default="przelot", verbose_name="Ujęcie")
    kind = models.CharField(max_length=6, choices=KIND_CHOICES, default="video", verbose_name="Wynik")
    resolution = models.CharField(max_length=10, choices=RES_CHOICES, default="1280x720", verbose_name="Rozdzielczość")
    seconds = models.PositiveSmallIntegerField(default=12, verbose_name="Długość [s]")
    scene_query = models.CharField(max_length=500, blank=True, default="",
                                   verbose_name="Parametry sceny (jak w odtwarzaczu 3D)")
    title = models.CharField(max_length=200, blank=True, default="", verbose_name="Tytuł")

    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="queued", db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    worker = models.CharField(max_length=80, blank=True, default="", verbose_name="Worker")
    claim_token = models.CharField(max_length=64, blank=True, default="", editable=False)
    attempts = models.PositiveSmallIntegerField(default=0, editable=False, verbose_name="Próby")   # US-015
    result = models.FileField(upload_to="renders/%Y/%m/", blank=True, verbose_name="Plik wyniku")
    log = models.TextField(blank=True, default="", verbose_name="Log workera")

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Zlecenie renderu"
        verbose_name_plural = "Zlecenia renderu"

    def __str__(self):
        return self.title or f"{self.get_preset_display()} — {self.model}"

    def new_claim(self):
        self.claim_token = secrets.token_urlsafe(24)
        return self.claim_token

    @property
    def extension(self):
        return "mp4" if self.kind == "video" else "png"

    @property
    def duration_s(self):
        if self.claimed_at and self.finished_at:
            return round((self.finished_at - self.claimed_at).total_seconds())
        return None
