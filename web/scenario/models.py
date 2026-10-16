"""Scenariusz: założenia wolumenów niezależne od layoutu (ten sam scenariusz testuje różne hale).

Dzień typowy i szczytowy mają własne plany przyjęć i wydań (auta OUT jak przyjęcia, profil zamówień,
paczek i zwrotów, cross-dock); normy wydajności i obsada (zmiany per proces) są wspólne dla scenariusza.
Wartości domyślne są syntetyczne (rząd wielkości z praktyki, bez danych firm).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .inbound import day_demand
from .outbound import day_outbound
from .staffing import PROCESSES
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

INBOUND_KINDS = [("container40", "Kontener 40' luzem"), ("truck33", "Auto 33-paletowe"), ("solo", "Solówka / bus"),
                 ("crossdock", "Cross-dock (auto)")]
OUTBOUND_KINDS = [("truck33", "Auto 33-paletowe"), ("solo", "Solówka / bus"), ("courier", "Kurier (odbiór paczek)"),
                  ("crossdock", "Cross-dock (auto)")]
# (przyjazdy min/śr/max, palet na przyjazd min/śr/max, okno od–do h, % mono-SKU, % kontroli, min kontroli)
INBOUND_DEFAULTS = {
    "container40": ((6, 8, 10), (38, 45, 52), (6, 14), 100, 10, 2.0),
    "truck33": ((6, 8, 10), (17, 26, 32), (8, 18), 75, 20, 2.0),
    "solo": ((3, 5, 8), (6, 12, 18), (7, 15), 60, 30, 2.0),
    "crossdock": ((2, 3, 4), (20, 26, 32), (6, 12), 100, 0, 0.0),
}
# (wyjazdy min/śr/max, palet na auto min/śr/max, okno załadunku od–cut-off h)
OUTBOUND_DEFAULTS = {
    "truck33": ((14, 18, 22), (24, 28, 32), (12, 20)),
    "solo": ((8, 10, 14), (6, 10, 14), (10, 18)),
    "courier": ((3, 4, 5), (0, 0, 0), (15, 18)),
    "crossdock": ((2, 3, 4), (20, 26, 32), (10, 16)),
}
# profil dnia typowego (min, śr, max); szczyt ×1,3 poza liniami na zamówienie
PROFILE_DEFAULTS = {"orders": (600, 800, 1000), "lines": (3, 5, 8), "parcels": (1500, 2200, 3000),
                    "returns": (60, 90, 140)}
# proces: [(od, do, przerwa min, osób)]
SHIFT_DEFAULTS = {
    "unload": [(6, 14, 30, 4), (14, 22, 30, 2)], "palletize": [(6, 14, 30, 6), (14, 22, 30, 3)],
    "inspect": [(6, 14, 30, 2)], "pick": [(6, 14, 30, 10), (14, 22, 30, 8)],
    "pack": [(6, 14, 30, 14), (14, 22, 30, 10)], "load": [(6, 14, 30, 2), (14, 22, 30, 4)],
    "returns": [(6, 14, 30, 2)],
}
LEVELS3 = ("min", "avg", "max")


def check_triples(obj, names):
    errors = []
    for name, label in names:
        lo, mid, hi = (getattr(obj, f"{name}_{x}") for x in LEVELS3)
        if None in (lo, mid, hi) or not 0 <= lo <= mid <= hi:
            errors.append(f"{label}: musi być 0 ≤ min ≤ śr. ≤ max.")
    return errors


def triple(obj, name):
    return tuple(getattr(obj, f"{name}_{x}") for x in LEVELS3)


class Scenario(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nazwa")
    description = models.TextField(blank=True, verbose_name="Opis")
    growth = models.FloatField(default=1.0, verbose_name="Mnożnik wzrostu",
                               help_text="Np. 1,3 = wolumeny +30 % (więcej przyjazdów).")
    seed = models.PositiveIntegerField(default=42, verbose_name="Ziarno losowania")
    shift_h = models.FloatField(default=8.0, verbose_name="Długość zmiany [h]")
    work_days = models.PositiveSmallIntegerField(default=5, verbose_name="Dni pracy w tygodniu")
    peak_days_year = models.PositiveSmallIntegerField(
        default=30, verbose_name="Dni szczytowe w roku",
        help_text="Koszty roczne: tyle dni liczonych jak dzień szczytowy, reszta dni pracy jak typowy.")
    # normy wydajności (przyjęcia)
    container_cartons_per_h = models.FloatField(default=500, verbose_name="Rozładunek kontenera: kartonów/h na osobę")
    container_people = models.PositiveSmallIntegerField(default=2, verbose_name="Osób przy kontenerze")
    cartons_per_pallet = models.FloatField(default=40, verbose_name="Średnio kartonów na paletę (z kontenera)")
    truck_min_per_pallet = models.FloatField(default=1.5, verbose_name="Rozładunek auta: min na paletę")
    palletize_cartons_per_h = models.FloatField(default=360, verbose_name="Paletyzacja ręczna: kartonów/h na osobę")
    repack_min_per_pallet = models.FloatField(default=15, verbose_name="Przepakowanie palety mieszanej: min")
    # normy wydajności (wydania, paczki, zwroty)
    load_min_per_pallet = models.FloatField(default=1.5, verbose_name="Załadunek: min na paletę")
    pick_lines_per_h = models.FloatField(default=60, verbose_name="Kompletacja: linii/h na osobę")
    wrap_min_per_pallet = models.FloatField(default=2, verbose_name="Owijanie palety kompletowanej: min")
    pack_min_per_parcel = models.FloatField(default=1.5, verbose_name="Pakowanie: min na paczkę")
    pack_min_per_line = models.FloatField(default=0.3, verbose_name="Pakowanie: min na linię")
    label_min_per_parcel = models.FloatField(default=0.3, verbose_name="Etykieta i nadanie: min na paczkę")
    courier_dock_min = models.FloatField(default=30, verbose_name="Odbiór kuriera: min przy doku")
    return_min = models.FloatField(default=6, verbose_name="Obsługa zwrotu: min")
    return_restock_pct = models.FloatField(default=70, verbose_name="Zwroty: % powrotu na skład")
    # flota (symulacja dnia): wózki do odkładania i zdejmowania palet, praca na baterii i ładowanie
    fleet_units = models.PositiveSmallIntegerField(default=12, verbose_name="Flota: wózków / AGV")
    fleet_min_per_move = models.FloatField(default=4, verbose_name="Flota: min na ruch palety (z dojazdem)")
    battery_h = models.FloatField(default=6, verbose_name="Flota: praca na baterii [h]")
    charge_h = models.FloatField(default=1.5, verbose_name="Flota: ładowanie [h]")
    # K1: typ floty z katalogu — wtedy czas ruchu liczony z prędkości/podnoszenia na layoucie, bateria z katalogu
    fleet_equipment = models.ForeignKey("equipment.Equipment", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="scenarios", verbose_name="Flota: sprzęt z katalogu")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    NORM_FIELDS = ["container_cartons_per_h", "container_people", "cartons_per_pallet", "truck_min_per_pallet",
                   "palletize_cartons_per_h", "repack_min_per_pallet", "load_min_per_pallet", "pick_lines_per_h",
                   "wrap_min_per_pallet", "pack_min_per_parcel", "pack_min_per_line", "label_min_per_parcel",
                   "courier_dock_min", "return_min"]
    FLEET_FIELDS = ["fleet_units", "fleet_min_per_move", "battery_h", "charge_h"]

    class Meta:
        ordering = ["-updated_at", "-pk"]
        verbose_name = "Scenariusz"
        verbose_name_plural = "Scenariusze"

    def __str__(self):
        return self.name

    def clean(self):
        if self.growth <= 0 or self.shift_h <= 0:
            raise ValidationError("Mnożnik wzrostu i długość zmiany muszą być dodatnie.")
        if any((getattr(self, f) or 0) <= 0 for f in [*self.NORM_FIELDS, *self.FLEET_FIELDS]):
            raise ValidationError("Normy wydajności i parametry floty muszą być dodatnie.")
        if not 0 <= (self.return_restock_pct or 0) <= 100 or not 1 <= (self.work_days or 0) <= 7:
            raise ValidationError("Zwroty na skład: 0–100 %; dni pracy w tygodniu: 1–7.")
        if (self.peak_days_year or 0) > self.work_days * 52:
            raise ValidationError(f"Dni szczytowe w roku: najwyżej {self.work_days * 52} (dni pracy × 52).")

    @property
    def norms(self):
        return {f: getattr(self, f) for f in [*self.NORM_FIELDS, "return_restock_pct"]}

    def sim_params(self):
        return {**self.norms, **{f: getattr(self, f) for f in self.FLEET_FIELDS}, "growth": self.growth}

    def shift_dicts(self):
        return [s.as_dict() for s in self.shifts.all()]

    def ensure_shifts(self):
        if not self.shifts.exists():
            Shift.objects.bulk_create(Shift(scenario=self, process=p, start_h=a, end_h=b, break_min=br, people=n)
                                      for p, rows in SHIFT_DEFAULTS.items() for a, b, br, n in rows)

    def ensure_days(self, with_defaults=True):
        """Dzień typowy i szczytowy; nowe dostają domyślne strumienie i profil (szczyt: wolumeny ×1,3)."""
        for kind, _ in ScenarioDay.KIND_CHOICES:
            day, created = ScenarioDay.objects.get_or_create(scenario=self, kind=kind)
            if created and with_defaults:
                day.fill_defaults(1.3 if kind == "peak" else 1.0)
        if with_defaults:
            self.ensure_shifts()


class ScenarioDay(models.Model):
    KIND_CHOICES = [("typical", "Dzień typowy"), ("peak", "Dzień szczytowy")]
    PROFILE = [("orders", "Zamówień/dzień"), ("lines", "Linii na zamówienie"), ("parcels", "Paczek/dzień"),
               ("returns", "Zwrotów/dzień")]
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="days")
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    orders_min = models.FloatField(default=0, verbose_name="Zamówień/dzień min")
    orders_avg = models.FloatField(default=0, verbose_name="Zamówień/dzień śr.")
    orders_max = models.FloatField(default=0, verbose_name="Zamówień/dzień max")
    lines_min = models.FloatField(default=0, verbose_name="Linii na zamówienie min")
    lines_avg = models.FloatField(default=0, verbose_name="Linii na zamówienie śr.")
    lines_max = models.FloatField(default=0, verbose_name="Linii na zamówienie max")
    parcels_min = models.FloatField(default=0, verbose_name="Paczek/dzień min")
    parcels_avg = models.FloatField(default=0, verbose_name="Paczek/dzień śr.")
    parcels_max = models.FloatField(default=0, verbose_name="Paczek/dzień max")
    returns_min = models.FloatField(default=0, verbose_name="Zwrotów/dzień min")
    returns_avg = models.FloatField(default=0, verbose_name="Zwrotów/dzień śr.")
    returns_max = models.FloatField(default=0, verbose_name="Zwrotów/dzień max")
    full_pallet_pct = models.FloatField(default=40, verbose_name="% palet OUT pełnych (bez kompletacji)")

    PROFILE_FIELDS = [f"{n}_{x}" for n, _ in PROFILE for x in LEVELS3] + ["full_pallet_pct"]

    class Meta:
        ordering = ["scenario", "-kind"]           # typical przed peak
        constraints = [models.UniqueConstraint(fields=["scenario", "kind"], name="scenario_day_unique")]

    def __str__(self):
        return f"{self.scenario} — {self.get_kind_display()}"

    def clean(self):
        errors = check_triples(self, self.PROFILE)
        if not 0 <= (self.full_pallet_pct or 0) <= 100:
            errors.append("% palet pełnych: 0–100.")
        if errors:
            raise ValidationError(errors)

    def fill_defaults(self, k):
        for stream_kind, (arr, pal, win, mono, insp, insp_min) in INBOUND_DEFAULTS.items():
            InboundStream.objects.create(
                day=self, kind=stream_kind,
                arrivals_min=round(arr[0] * k), arrivals_avg=round(arr[1] * k), arrivals_max=round(arr[2] * k),
                pallets_min=pal[0], pallets_avg=pal[1], pallets_max=pal[2],
                window_from=win[0], window_to=win[1], mono_pct=mono, inspect_pct=insp, inspect_min=insp_min)
        for stream_kind, (dep, pal, win) in OUTBOUND_DEFAULTS.items():
            OutboundStream.objects.create(
                day=self, kind=stream_kind,
                departures_min=round(dep[0] * k), departures_avg=round(dep[1] * k), departures_max=round(dep[2] * k),
                pallets_min=pal[0], pallets_avg=pal[1], pallets_max=pal[2], window_from=win[0], window_to=win[1])
        for name, values in PROFILE_DEFAULTS.items():
            kk = 1.0 if name == "lines" else k
            for x, v in zip(LEVELS3, values, strict=True):
                setattr(self, f"{name}_{x}", round(v * kk))
        self.save()

    def demand(self, level):
        streams = [s.as_dict() for s in self.inbound.all()]
        sc = self.scenario
        return day_demand(streams, sc.norms, growth=sc.growth, level=level, shift_h=sc.shift_h)

    def profile(self):
        return {**{n: triple(self, n) for n, _ in self.PROFILE}, "full_pallet_pct": self.full_pallet_pct}

    def sim_day(self):
        return {"inbound": [s.as_dict() for s in self.inbound.all()],
                "outbound": [s.as_dict() for s in self.outbound.all()], "profile": self.profile()}

    def outbound_demand(self, level):
        sc = self.scenario
        return day_outbound([s.as_dict() for s in self.outbound.all()], self.profile(), sc.norms,
                            growth=sc.growth, level=level)


class InboundStream(models.Model):
    day = models.ForeignKey(ScenarioDay, on_delete=models.CASCADE, related_name="inbound")
    kind = models.CharField(max_length=12, choices=INBOUND_KINDS, verbose_name="Typ dostawy")
    arrivals_min = models.FloatField(default=0, verbose_name="Przyjazdów min")
    arrivals_avg = models.FloatField(default=0, verbose_name="Przyjazdów śr.")
    arrivals_max = models.FloatField(default=0, verbose_name="Przyjazdów max")
    pallets_min = models.FloatField(default=0, verbose_name="Palet na przyjazd min")
    pallets_avg = models.FloatField(default=0, verbose_name="Palet na przyjazd śr.")
    pallets_max = models.FloatField(default=0, verbose_name="Palet na przyjazd max")
    window_from = models.FloatField(default=6, verbose_name="Okno awizacji od")
    window_to = models.FloatField(default=14, verbose_name="Okno awizacji do")
    mono_pct = models.FloatField(default=100, verbose_name="% palet mono-SKU")
    inspect_pct = models.FloatField(default=10, verbose_name="% palet do kontroli")
    inspect_min = models.FloatField(default=2, verbose_name="Kontrola: min na paletę")

    class Meta:
        ordering = ["day", "pk"]
        verbose_name = "Strumień przyjęć"
        verbose_name_plural = "Strumienie przyjęć"

    def clean(self):
        errors = check_triples(self, (("arrivals", "Liczba przyjazdów"), ("pallets", "Liczba palet na przyjazd")))
        if not 0 <= (self.window_from or 0) < (self.window_to or 0) <= 24:
            errors.append("Okno awizacji: od < do, w granicach 0–24 h.")
        for f, label in (("mono_pct", "% mono-SKU"), ("inspect_pct", "% kontroli")):
            if not 0 <= (getattr(self, f) or 0) <= 100:
                errors.append(f"{label}: 0–100.")
        if (self.inspect_min or 0) < 0:
            errors.append("Czas kontroli nie może być ujemny.")
        if errors:
            raise ValidationError(errors)

    def as_dict(self):
        return {"kind": self.kind, "arrivals": triple(self, "arrivals"), "pallets": triple(self, "pallets"),
                "window": (self.window_from, self.window_to), "mono_pct": self.mono_pct,
                "inspect_pct": self.inspect_pct, "inspect_min": self.inspect_min}


class OutboundStream(models.Model):
    """Auta wyjazdowe — jak przyjęcia. Koniec okna = cut-off (odjazd / odbiór kuriera)."""
    day = models.ForeignKey(ScenarioDay, on_delete=models.CASCADE, related_name="outbound")
    kind = models.CharField(max_length=12, choices=OUTBOUND_KINDS, verbose_name="Typ auta")
    departures_min = models.FloatField(default=0, verbose_name="Wyjazdów min")
    departures_avg = models.FloatField(default=0, verbose_name="Wyjazdów śr.")
    departures_max = models.FloatField(default=0, verbose_name="Wyjazdów max")
    pallets_min = models.FloatField(default=0, verbose_name="Palet na auto min")
    pallets_avg = models.FloatField(default=0, verbose_name="Palet na auto śr.")
    pallets_max = models.FloatField(default=0, verbose_name="Palet na auto max")
    window_from = models.FloatField(default=12, verbose_name="Załadunek od")
    window_to = models.FloatField(default=20, verbose_name="Cut-off")

    class Meta:
        ordering = ["day", "pk"]
        verbose_name = "Strumień wydań"
        verbose_name_plural = "Strumienie wydań"

    def clean(self):
        errors = check_triples(self, (("departures", "Liczba wyjazdów"), ("pallets", "Liczba palet na auto")))
        if not 0 <= (self.window_from or 0) < (self.window_to or 0) <= 24:
            errors.append("Okno załadunku: od < cut-off, w granicach 0–24 h.")
        if errors:
            raise ValidationError(errors)

    def as_dict(self):
        return {"kind": self.kind, "departures": triple(self, "departures"), "pallets": triple(self, "pallets"),
                "window": (self.window_from, self.window_to)}


class ScenarioRun(models.Model):
    """Wynik symulacji dnia scenariusza na modelu hali (S3a): KPI średnia/najgorszy, oś czasu przebiegu
    reprezentatywnego, wąskie gardła; `events` — zdarzenia tego przebiegu dla animacji (S4)."""
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="runs")
    day_kind = models.CharField(max_length=8, choices=ScenarioDay.KIND_CHOICES)
    model = models.ForeignKey("twin.WarehouseModel", on_delete=models.CASCADE, related_name="scenario_runs")
    runs = models.PositiveSmallIntegerField(default=12)
    seed = models.PositiveIntegerField(default=42)
    duration_s = models.FloatField(default=0)
    result = models.JSONField(default=dict)
    events = models.JSONField(default=list)
    # R3: czy są zdarzenia animacji — bez wczytywania ciężkiej listy `events` (widoki ją odraczają)
    has_events = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Symulacja scenariusza"
        verbose_name_plural = "Symulacje scenariuszy"

    def __str__(self):
        return f"{self.scenario} — {self.get_day_kind_display()} na „{self.model}”"


class ScenarioFleet(models.Model):
    """K3: grupa floty mieszanej — sprzęt z katalogu × sztuk; rola w symulacji z typu (`catalog.FLEET_ROLE`).
    Bez grup scenariusz liczy jedną flotę z pól `fleet_*` / `fleet_equipment` jak dotąd."""
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="fleet")
    equipment = models.ForeignKey("equipment.Equipment", on_delete=models.CASCADE, related_name="scenario_fleets",
                                  verbose_name="Sprzęt z katalogu")
    units = models.PositiveSmallIntegerField(default=1, verbose_name="Sztuk")

    class Meta:
        ordering = ["scenario", "pk"]
        verbose_name = "Grupa floty"
        verbose_name_plural = "Flota mieszana"

    def clean(self):
        if not self.units:
            raise ValidationError("Liczba sztuk musi być dodatnia.")


class Shift(models.Model):
    """Zmiana procesu: godziny, przerwa, zakładana obsada. Koniec ≤ początek = zmiana przez północ."""
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="shifts")
    process = models.CharField(max_length=10, choices=PROCESSES, verbose_name="Proces")
    start_h = models.FloatField(default=6, verbose_name="Od")
    end_h = models.FloatField(default=14, verbose_name="Do")
    break_min = models.FloatField(default=30, verbose_name="Przerwa [min]")
    people = models.PositiveSmallIntegerField(default=1, verbose_name="Osób")

    class Meta:
        ordering = ["scenario", "process", "start_h", "pk"]
        verbose_name = "Zmiana"
        verbose_name_plural = "Zmiany"

    def clean(self):
        a, b = self.start_h or 0, self.end_h or 0
        length = b - a + (24 if b <= a else 0)
        errors = []
        if not (0 <= a < 24 and 0 <= b <= 24) or a == b:
            errors.append("Godziny zmiany: 0–24, początek ≠ koniec.")
        if (self.break_min or 0) < 0 or (self.break_min or 0) / 60 >= length:
            errors.append("Przerwa musi być krótsza niż zmiana.")
        if errors:
            raise ValidationError(errors)

    def as_dict(self):
        return {"process": self.process, "start_h": self.start_h, "end_h": self.end_h,
                "break_min": self.break_min, "people": self.people}


class Showcase(models.Model):
    """Prezentacja 3D dla zarządu (P1): model hali (+ działka) i opcjonalnie wynik symulacji; slajdy to lista
    JSON (`showcase.clean_slides`), kolejność = kolejność listy. Zamiennik filmu — F5 `studio` zostaje osobno."""
    title = models.CharField(max_length=200, verbose_name="Tytuł")
    model = models.ForeignKey("twin.WarehouseModel", on_delete=models.CASCADE, related_name="showcases",
                              verbose_name="Model hali")
    run = models.ForeignKey(ScenarioRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="showcases",
                            verbose_name="Wynik symulacji")
    # US-025: kiedy przypięty wynik zniknął (usunięty scenariusz albo przebieg) — pokaz traci wyniki bez ostrzeżenia
    run_removed_at = models.DateTimeField(null=True, blank=True, editable=False)
    slides = models.JSONField(default=list)
    # P3: publiczny link tylko do odczytu (bez logowania) — losowy token w adresie, wygasa; brak tokenu = wyłączony
    share_token = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    share_expires = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        verbose_name = "Prezentacja 3D"
        verbose_name_plural = "Prezentacje 3D"

    def __str__(self):
        return self.title


@receiver(pre_delete, sender=ScenarioRun)
def _mark_showcases_without_run(sender, instance, **kwargs):
    """US-025: prezentacja z tym wynikiem dostaje znacznik — pokaz ostrzeże Projektanta."""
    Showcase.objects.filter(run=instance).update(run_removed_at=timezone.now())
