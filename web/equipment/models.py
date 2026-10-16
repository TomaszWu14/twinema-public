"""Katalog sprzętu (K1): klasy systemowe (anonimowe, z migracji) i własne modele użytkownika.

Osobna aplikacja, bo katalog zasila dwa moduły: layout hali (`twin` — alejka, wysokość, udźwig) i symulację
scenariusza (`scenario` — czas ruchu palety, bateria). Sam niczego nie importuje z tamtych.
"""
from django.conf import settings
from django.db import models

from .catalog import ATTACHMENTS, KINDS, RACK_CATEGORY, apply_attachments

PARAM_FIELDS = ["speed_loaded_kmh", "speed_empty_kmh", "lift_speed_ms", "lower_speed_ms", "max_lift_m",
                "capacity_kg", "lift_curve", "aisle_m", "pick_s", "drop_s", "battery_h", "charge_h",
                "turn_radius_m", "length_m", "width_m", "throughput_h"]


class Equipment(models.Model):
    kind = models.CharField(max_length=16, choices=KINDS, verbose_name="Typ")
    name = models.CharField(max_length=120, verbose_name="Nazwa")
    # K2: producent tylko jako tekst w bazie użytkownika (własne modele) — nigdy w repo / danych demo
    manufacturer = models.CharField(max_length=80, blank=True, default="", verbose_name="Producent")
    attachments = models.JSONField(default=list, blank=True, verbose_name="Osprzęt",
                                   help_text="Kody osprzętu — zmniejszają udźwig i wydłużają obsługę palety.")
    is_system = models.BooleanField(default=False, editable=False, verbose_name="Klasa systemowa")
    speed_loaded_kmh = models.FloatField(verbose_name="Jazda z ładunkiem [km/h]")
    speed_empty_kmh = models.FloatField(verbose_name="Jazda bez ładunku [km/h]")
    lift_speed_ms = models.FloatField(null=True, blank=True, verbose_name="Podnoszenie [m/s]")
    lower_speed_ms = models.FloatField(null=True, blank=True, verbose_name="Opuszczanie [m/s]")
    max_lift_m = models.FloatField(null=True, blank=True, verbose_name="Maks. wysokość podnoszenia [m]")
    capacity_kg = models.PositiveIntegerField(verbose_name="Udźwig nominalny [kg]")
    lift_curve = models.JSONField(default=list, blank=True, verbose_name="Redukcja udźwigu",
                                  help_text="Punkty [wysokość m, udźwig kg], np. [[6, 1600], [10, 1000]].")
    aisle_m = models.FloatField(null=True, blank=True, verbose_name="Wymagana alejka robocza Ast [m]")
    pick_s = models.FloatField(null=True, blank=True, verbose_name="Pobranie palety [s]")
    drop_s = models.FloatField(null=True, blank=True, verbose_name="Odłożenie palety [s]")
    battery_h = models.FloatField(null=True, blank=True, verbose_name="Praca na baterii [h]")
    charge_h = models.FloatField(null=True, blank=True, verbose_name="Ładowanie / wymiana [h]")
    turn_radius_m = models.FloatField(null=True, blank=True, verbose_name="Promień skrętu [m]")
    length_m = models.FloatField(null=True, blank=True, verbose_name="Długość [m]")
    width_m = models.FloatField(null=True, blank=True, verbose_name="Szerokość [m]")
    throughput_h = models.PositiveIntegerField(null=True, blank=True, verbose_name="Wydajność nominalna [szt./h]")
    # C1: widełki kosztów (min–max) — CAPEX z zakupu, OPEX z godziny pracy (energia + serwis)
    cost_purchase = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        verbose_name="Zakup od [zł]")
    cost_purchase_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                            verbose_name="Zakup do [zł]")
    cost_per_hour = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                        verbose_name="Godzina pracy od [zł]")
    cost_per_hour_max = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                            verbose_name="Godzina pracy do [zł]")
    notes = models.TextField(blank=True, verbose_name="Uwagi")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "-is_system", "name"]
        verbose_name = "Sprzęt"
        verbose_name_plural = "Katalog sprzętu"
        # US-022: import aktualizuje własny model po nazwie — nazwa musi wskazywać jeden model
        constraints = [models.UniqueConstraint(fields=["name"], condition=models.Q(is_system=False),
                                               name="equipment_own_name_unique")]

    def __str__(self):
        return self.name

    @property
    def rack_category(self):
        return RACK_CATEGORY.get(self.kind)

    def cost_range(self, low, high):
        """(od, do) jako float; brak „do” = „od”; brak obu = None."""
        a, b = getattr(self, low), getattr(self, high)
        if a is None and b is None:
            return None
        a = float(a if a is not None else b)
        return a, float(b if b is not None else a)

    @property
    def attachment_labels(self):
        return [ATTACHMENTS[c][0] for c in self.attachments or [] if c in ATTACHMENTS]

    def params(self):
        """Parametry robocze (z osprzętem) — jedno źródło dla layoutu i symulacji."""
        raw = {f: getattr(self, f) for f in PARAM_FIELDS} | {"id": self.pk, "kind": self.kind, "name": self.name}
        return apply_attachments(raw, self.attachments)


class CostRate(models.Model):
    """Stawka kosztowa (C1) jako widełki min–max — wartości domyślne syntetyczne, przybliżone (bez cenników firm)."""
    key = models.CharField(max_length=24, unique=True, editable=False)
    label = models.CharField(max_length=120, editable=False)
    unit = models.CharField(max_length=24, editable=False)
    low = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Od")
    high = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Do")
    order = models.PositiveSmallIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["order", "key"]
        verbose_name = "Stawka kosztowa"
        verbose_name_plural = "Stawki kosztowe"

    def __str__(self):
        return self.label

    @classmethod
    def as_dict(cls):
        return {r.key: (float(r.low), float(r.high)) for r in cls.objects.all()}
