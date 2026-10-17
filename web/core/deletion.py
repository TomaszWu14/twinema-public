"""US-004: ekran potwierdzenia usunięcia z listą obiektów usuwanych razem z obiektem i tracących powiązanie.
Liczy się tylko to, co dotyczy użytkownika (bez technicznych tabel pośrednich); pozycje z zerem pomijane."""
from django.shortcuts import render


def confirm(request, *, title, name, removed, detached=(), cancel_url, confirm_label="Tak, usuń"):
    return render(request, "core/confirm_delete.html", {
        "title": title, "name": name, "cancel_url": cancel_url, "confirm_label": confirm_label,
        "removed": [(label, n) for label, n in removed if n],
        "detached": [(label, n) for label, n in detached if n]})


def hall_effects(wm):
    removed = [("regały", wm.racks.count()), ("elementy hali (doki, strefy, drogi)", wm.features.count()),
               ("wyniki symulacji", wm.scenario_runs.count()), ("prezentacje 3D", wm.showcases.count()),
               ("prezentacje filmowe", wm.presentations.count()), ("zlecenia renderu", wm.render_jobs.count())]
    detached = [("warianty projektu (tracą model bazowy)", wm.design_variants.count())]
    return removed, detached


def scenario_effects(sc):
    from scenario.models import Showcase
    removed = [("wyniki symulacji", sc.runs.count()), ("zmiany obsady", sc.shifts.count()),
               ("grupy floty mieszanej", sc.fleet.count())]
    detached = [("prezentacje 3D (tracą wynik symulacji)", Showcase.objects.filter(run__scenario=sc).count())]
    return removed, detached


def equipment_effects(eq):
    removed = [("grupy floty mieszanej w scenariuszach", eq.scenario_fleets.count())]
    detached = [("regały (wracają do ustawień ogólnych)", eq.racks.count()),
                ("scenariusze z flotą jednorodną (wracają do ustawień ogólnych)", eq.scenarios.count())]
    return removed, detached
