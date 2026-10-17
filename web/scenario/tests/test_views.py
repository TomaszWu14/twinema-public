"""Scenariusze: tworzenie z domyślnymi, role, edycja planu, walidacja min ≤ śr ≤ max, kopia, demo."""
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.roles import GROUP_DESIGNER, GROUP_VIEWER
from scenario.models import InboundStream, OutboundStream, Scenario, Shift
from scenario.views import HourField


def hhmm(h):
    m = round(h * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


class ScenarioViewTests(TestCase):
    def setUp(self):
        self.designer = User.objects.create_user("proj", password="x")
        self.designer.groups.add(Group.objects.create(name=GROUP_DESIGNER))
        self.viewer = User.objects.create_user("zarzad", password="x")
        self.viewer.groups.add(Group.objects.create(name=GROUP_VIEWER))
        self.client.force_login(self.designer)

    def _create(self, name="Rok bazowy"):
        self.client.post(reverse("scenario:create"), {"name": name})
        return Scenario.objects.get(name=name)

    def _day_post(self, sc, kind, rows):
        streams = list(sc.days.get(kind=kind).inbound.all())
        data = {f"{kind}-TOTAL_FORMS": len(rows), f"{kind}-INITIAL_FORMS": len(streams),
                f"{kind}-MIN_NUM_FORMS": 0, f"{kind}-MAX_NUM_FORMS": 1000}
        for i, row in enumerate(rows):
            data.update({f"{kind}-{i}-{k}": v for k, v in row.items()})
        return self.client.post(reverse("scenario:day_save", args=[sc.pk, kind]), data, follow=True)

    @staticmethod
    def _row(s, **over):
        row = {k: getattr(s, k) for k in ("kind", "arrivals_min", "arrivals_avg", "arrivals_max", "pallets_min",
                                          "pallets_avg", "pallets_max", "window_from", "window_to", "mono_pct",
                                          "inspect_pct", "inspect_min")}
        row["window_from"], row["window_to"] = hhmm(s.window_from), hhmm(s.window_to)
        return {"id": s.pk, **row, **over}

    def test_create_seeds_typical_and_peak_with_results(self):
        sc = self._create()
        self.assertEqual(sorted(sc.days.values_list("kind", flat=True)), ["peak", "typical"])
        self.assertEqual(sc.days.get(kind="typical").inbound.count(), 4)
        peak = sc.days.get(kind="peak").inbound.get(kind="container40")
        self.assertEqual(peak.arrivals_avg, 10)                       # 8 × 1,3
        r = self.client.get(reverse("scenario:detail", args=[sc.pk]))
        self.assertContains(r, "Doki kontenerowe IN")
        self.assertContains(r, "Zapisz plan przyjęć")
        self.assertContains(self.client.get(reverse("core:home")), reverse("scenario:list"))

    def test_viewer_sees_results_but_no_forms_and_cannot_post(self):
        sc = self._create()
        self.client.force_login(self.viewer)
        r = self.client.get(reverse("scenario:detail", args=[sc.pk]))
        self.assertContains(r, "Palet przyjętych / dzień")
        self.assertContains(r, "Założenia przyjęć")
        self.assertNotContains(r, "Zapisz plan przyjęć")
        self.assertEqual(self.client.post(reverse("scenario:copy", args=[sc.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("scenario:create"), {"name": "X"}).status_code, 403)

    def test_edit_stream_recalculates(self):
        sc = self._create()
        c = sc.days.get(kind="typical").inbound.get(kind="container40")
        others = [self._row(s) for s in sc.days.get(kind="typical").inbound.exclude(pk=c.pk)]
        self._day_post(sc, "typical", [self._row(c, arrivals_avg=9, arrivals_max=12), *others])
        c.refresh_from_db()
        self.assertEqual((c.arrivals_avg, c.arrivals_max), (9, 12))
        self.assertEqual(sc.days.get(kind="typical").demand("avg")["rows"][0]["arrivals"], 9)

    def test_min_avg_max_order_is_validated(self):
        sc = self._create()
        c = sc.days.get(kind="typical").inbound.get(kind="truck33")
        others = [self._row(s) for s in sc.days.get(kind="typical").inbound.exclude(pk=c.pk)]
        r = self._day_post(sc, "typical", [self._row(c, pallets_min=30, pallets_avg=20), *others])
        self.assertContains(r, "min ≤ śr. ≤ max")
        c.refresh_from_db()
        self.assertEqual(c.pallets_min, 17)
        bad = InboundStream(day=c.day, kind="solo", arrivals_min=1, arrivals_avg=1, arrivals_max=1, pallets_min=1,
                            pallets_avg=1, pallets_max=1, window_from=14, window_to=6)
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_invalid_form_keeps_typed_values_once(self):
        """US-021: po błędzie walidacji formularz wraca z wpisanymi danymi; po kolejnym wejściu — dane z bazy."""
        sc = self._create()
        c = sc.days.get(kind="typical").inbound.get(kind="truck33")
        others = [self._row(s) for s in sc.days.get(kind="typical").inbound.exclude(pk=c.pk)]
        r = self._day_post(sc, "typical", [self._row(c, pallets_min=30, pallets_avg=20), *others])
        fs = next(d["inbound"] for d in r.context["day_forms"] if d["day"].kind == "typical")
        self.assertTrue(fs.is_bound)
        self.assertEqual(fs.data["typical-0-pallets_min"], "30")             # wpisana wartość, nie z bazy
        again = self.client.get(reverse("scenario:detail", args=[sc.pk]))
        fs = next(d["inbound"] for d in again.context["day_forms"] if d["day"].kind == "typical")
        self.assertFalse(fs.is_bound)

    def test_save_params_and_reject_zero_norm(self):
        sc = self._create()
        data = {"name": sc.name, "description": "", "growth": 1.3, "seed": 7, "shift_h": 8, "work_days": 6,
                "return_restock_pct": 70,
                **{f: getattr(sc, f) for f in [*Scenario.NORM_FIELDS, *Scenario.FLEET_FIELDS]}}
        self.client.post(reverse("scenario:save", args=[sc.pk]), data)
        sc.refresh_from_db()
        self.assertEqual((sc.growth, sc.seed), (1.3, 7))
        r = self.client.post(reverse("scenario:save", args=[sc.pk]), {**data, "cartons_per_pallet": 0}, follow=True)
        self.assertContains(r, "muszą być dodatnie")
        self.assertEqual(r.context["form"]["cartons_per_pallet"].value(), "0")   # US-021: wpisana wartość zostaje

    def test_copy_is_deep_and_independent(self):
        sc = self._create()
        self.client.post(reverse("scenario:copy", args=[sc.pk]))
        copy = Scenario.objects.get(name="Rok bazowy (kopia)")
        self.assertEqual(copy.days.count(), 2)
        self.assertEqual(InboundStream.objects.filter(day__scenario=copy).count(), 8)
        self.assertEqual(OutboundStream.objects.filter(day__scenario=copy).count(), 8)
        self.assertEqual(copy.shifts.count(), sc.shifts.count())
        self.assertEqual(copy.days.get(kind="typical").parcels_avg, 2200)
        InboundStream.objects.filter(day__scenario=copy).delete()
        copy.shifts.all().delete()
        self.assertEqual(InboundStream.objects.filter(day__scenario=sc).count(), 8)
        self.assertGreater(sc.shifts.count(), 0)

    def test_delete(self):
        sc = self._create()
        self.client.post(reverse("scenario:delete", args=[sc.pk]))
        self.assertFalse(Scenario.objects.exists())

    def test_demo_command_is_idempotent(self):
        out = StringIO()
        call_command("demo_scenariusz", stdout=out)
        call_command("demo_scenariusz", stdout=out)
        sc = Scenario.objects.get()
        self.assertEqual(InboundStream.objects.filter(day__scenario=sc).count(), 8)
        typical = sc.days.get(kind="typical").demand("avg")
        self.assertEqual(typical["pallets_in"], 8 * 45 + 8 * 26 + 6 * 12 + 3 * 26)
        o = sc.days.get(kind="typical").outbound_demand("avg")
        self.assertEqual((o["pallets_out"], o["parcels"]), (18 * 28 + 10 * 10 + 3 * 26, 2200))
        self.assertTrue(sc.shifts.exists())
        self.assertIn("osobogodzin", out.getvalue())

    # ── S2b: wydania, paczki, zwroty, obsada, godziny GG:MM ─────────────────────────
    def _out_post(self, sc, kind, profile_over=None, rows=None):
        day = sc.days.get(kind=kind)
        streams = list(day.outbound.all())
        if rows is None:
            rows = [{"id": s.pk, "kind": s.kind, "departures_min": s.departures_min,
                     "departures_avg": s.departures_avg, "departures_max": s.departures_max,
                     "pallets_min": s.pallets_min, "pallets_avg": s.pallets_avg, "pallets_max": s.pallets_max,
                     "window_from": hhmm(s.window_from), "window_to": hhmm(s.window_to)} for s in streams]
        p = f"{kind}-out"
        data = {f"{p}-TOTAL_FORMS": len(rows), f"{p}-INITIAL_FORMS": len(streams),
                f"{p}-MIN_NUM_FORMS": 0, f"{p}-MAX_NUM_FORMS": 1000}
        for i, row in enumerate(rows):
            data.update({f"{p}-{i}-{k}": v for k, v in row.items()})
        profile = {f: getattr(day, f) for f in day.PROFILE_FIELDS} | (profile_over or {})
        data.update({f"{kind}-p-{k}": v for k, v in profile.items()})
        return self.client.post(reverse("scenario:outbound_save", args=[sc.pk, kind]), data, follow=True)

    def test_create_seeds_outbound_profile_and_shifts(self):
        sc = self._create()
        day = sc.days.get(kind="typical")
        self.assertEqual(set(day.outbound.values_list("kind", flat=True)), {"truck33", "solo", "courier", "crossdock"})
        self.assertEqual((day.parcels_avg, sc.days.get(kind="peak").parcels_avg), (2200, 2860))
        self.assertTrue(sc.shifts.filter(process="pack").exists())
        r = self.client.get(reverse("scenario:detail", args=[sc.pk]))
        for text in ("Palet wydanych / dzień", "Paczek / dzień", "Doki OUT", "Obsada: zakładana vs potrzebna",
                     "Zapisz wydania", "Zapisz obsadę", 'value="06:00"'):
            self.assertContains(r, text)

    def test_save_outbound_profile_and_streams(self):
        sc = self._create()
        r = self._out_post(sc, "typical", {"parcels_avg": 2500, "parcels_max": 3200})
        self.assertContains(r, "Zapisano wydania")
        day = sc.days.get(kind="typical")
        self.assertEqual((day.parcels_avg, day.parcels_max), (2500, 3200))
        self.assertEqual(day.outbound_demand("avg")["parcels"], 2500)
        bad = self._out_post(sc, "typical", {"orders_min": 900, "orders_avg": 800})
        self.assertContains(bad, "min ≤ śr. ≤ max")
        self.assertEqual(sc.days.get(kind="typical").orders_min, 600)

    def test_hours_as_hhmm(self):
        sc = self._create()
        truck = sc.days.get(kind="typical").outbound.get(kind="truck33")
        rows = [{"id": truck.pk, "kind": "truck33", "departures_min": 1, "departures_avg": 2, "departures_max": 3,
                 "pallets_min": 10, "pallets_avg": 20, "pallets_max": 30, "window_from": "12:30",
                 "window_to": "19:45"}]
        self._out_post(sc, "typical", rows=rows)
        truck.refresh_from_db()
        self.assertEqual((truck.window_from, truck.window_to), (12.5, 19.75))
        f = HourField()
        self.assertEqual((f.clean("24:00"), f.clean("7"), f.prepare_value(13.5)), (24, 7, "13:30"))
        for bad in ("13,5", "25:00", "12:75"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                f.clean(bad)

    def test_shifts_save_and_shortage_flag(self):
        sc = self._create()
        shifts = list(sc.shifts.all())
        data = {"shift-TOTAL_FORMS": len(shifts), "shift-INITIAL_FORMS": len(shifts),
                "shift-MIN_NUM_FORMS": 0, "shift-MAX_NUM_FORMS": 1000}
        for i, s in enumerate(shifts):
            data.update({f"shift-{i}-id": s.pk, f"shift-{i}-process": s.process,
                         f"shift-{i}-start_h": hhmm(s.start_h), f"shift-{i}-end_h": hhmm(s.end_h),
                         f"shift-{i}-break_min": s.break_min,
                         f"shift-{i}-people": 1 if s.process == "pack" else s.people})
        r = self.client.post(reverse("scenario:shifts_save", args=[sc.pk]), data, follow=True)
        self.assertContains(r, "Zapisano obsadę")
        self.assertEqual(set(Shift.objects.filter(scenario=sc, process="pack").values_list("people", flat=True)), {1})
        self.assertContains(r, "(niedobór)")
        self.assertContains(r, "Paczki przed cut-off")

    def test_viewer_sees_outbound_summary_without_forms(self):
        sc = self._create()
        self.client.force_login(self.viewer)
        r = self.client.get(reverse("scenario:detail", args=[sc.pk]))
        self.assertContains(r, "Założenia przyjęć i wydań")
        self.assertContains(r, "Obsada: zakładana vs potrzebna")
        self.assertNotContains(r, "Zapisz obsadę")
        self.assertEqual(self.client.post(reverse("scenario:shifts_save", args=[sc.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("scenario:outbound_save", args=[sc.pk, "typical"])).status_code,
                         403)


class R4FlowTests(TestCase):
    """R4: „Wczytaj demo” zamiast manage.py, CTA model hali → scenariusz z wybraną halą, pusty stan bez hali."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_superuser("a", "a@x.pl", "x"))

    def test_empty_list_offers_demo_button_and_demo_loads(self):
        from django.urls import reverse
        r = self.client.get(reverse("scenario:list"))
        self.assertContains(r, "Wczytaj demo")
        self.assertNotContains(r, "manage.py")
        r = self.client.post(reverse("scenario:demo"))
        self.assertEqual(r.status_code, 302)
        self.assertContains(self.client.get(r["Location"]), "Uruchom symulację")

    def test_detail_without_halls_links_to_generator(self):
        from django.urls import reverse

        from scenario.models import Scenario
        self.client.post(reverse("scenario:create"), {"name": "S"})
        r = self.client.get(reverse("scenario:detail", args=[Scenario.objects.get().pk]))
        self.assertContains(r, reverse("twin:warehouse_model_generator"))
        self.assertNotContains(r, "Uruchom symulację")

    def test_model_cta_preselects_hall(self):
        from django.urls import reverse

        from scenario.models import Scenario
        from twin.models import WarehouseModel
        a = WarehouseModel.objects.create(name="A", floor_width_m=40, floor_depth_m=30)
        b = WarehouseModel.objects.create(name="B", floor_width_m=40, floor_depth_m=30)
        self.assertContains(self.client.get(reverse("twin:warehouse_model_view", args=[b.pk])),
                            f'{reverse("scenario:list")}?model={b.pk}')
        self.client.post(reverse("scenario:create"), {"name": "S"})
        sc = Scenario.objects.get()
        lst = self.client.get(reverse("scenario:list"), {"model": b.pk})
        self.assertContains(lst, f'{reverse("scenario:detail", args=[sc.pk])}?model={b.pk}')
        r = self.client.get(reverse("scenario:detail", args=[sc.pk]), {"model": b.pk})
        self.assertEqual(r.context["sim_form"].initial["model"], b.pk)
        self.assertNotEqual(a.pk, b.pk)
