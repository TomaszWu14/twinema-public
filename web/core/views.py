from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .demo import DEMO_USER, demo_showcase, exposure_reasons
from .models import AuditEvent, Job
from .roles import GROUP_ADMIN, GROUP_DESIGNER, GROUP_VIEWER, admin_only, any_role, has_role

# Moduły platformy w kolejności przepływu pracy — jedno źródło dla nawigacji w nagłówku i kafli strony
# głównej (R4: te same nazwy). `apps` / `match` = kiedy pozycja jest aktywna (patrz `active_module`).
MODULES = [
    {"key": "dane", "name": "Dane", "desc": "Materiały, master lokalizacji, stany — importy z plików z raportem.",
     "url": "masterdata:home", "apps": {"masterdata"}},
    {"key": "model", "name": "Modele hal", "desc": "Hala od zera albo z danych: regały, strefy, pola odkładcze, działka.",
     "url": "twin:warehouse_model_list", "apps": {"twin"}},
    {"key": "scenariusze", "name": "Scenariusze", "desc": "Wolumeny dnia typowego i szczytowego, symulacja dnia, koszty.",
     "url": "scenario:list", "apps": {"scenario"}},
    {"key": "projektowanie", "name": "Projektowanie", "desc": "Dzień projektowy z danych, flota, kalibracja, porównanie wariantów.",
     "url": "twin:design_hub", "match": ("design_",)},
    {"key": "zadania", "name": "Zadania EWM", "desc": "Import zadań magazynowych: profil, prognoza i symulacja dnia.",
     "url": "twin:ewm_tasks_list", "match": ("ewm_tasks",), "designer": True},
    {"key": "sprzet", "name": "Sprzęt", "desc": "Wózki, AGV/AMR z osprzętem: prędkości, podnoszenie, udźwig, alejka, koszty.",
     "url": "equipment:list", "apps": {"equipment"}},
    {"key": "prezentacje", "name": "Prezentacje", "desc": "Pokaz 3D dla zarządu: ujęcia hali, wyniki dnia, szczyt, wnioski.",
     "url": "scenario:showcase_list", "match": ("showcase",)},
    {"key": "ml", "name": "Prognozy i ML", "desc": "Holt-Winters kontra baseline, segmentacja SKU pod rozmieszczenie.",
     "url": "ml:home", "apps": {"ml"}},
    {"key": "render", "name": "Render", "desc": "Blender: ujęcia i animacje przepływów (worker na PC).",
     "url": "render:jobs", "apps": {"render"}},
    {"key": "studio", "name": "Studio", "desc": "Scenariusz, napisy, montaż — film i deck.",
     "url": "studio:list", "apps": {"studio"}},
    {"key": "dziennik", "name": "Dziennik", "desc": "Kto usunął dane, zaimportował plik albo udostępnił link publiczny.",
     "url": "core:audit_log", "match": ("audit_log",), "admin": True},
]


def active_module(rm):
    """Klucz modułu dla bieżącego widoku: najpierw dopasowanie po nazwie URL (moduły w obrębie jednej appki:
    prezentacje w `scenario`, projektowanie i zadania EWM w `twin`), potem po appce. Brak → None."""
    if rm is None:
        return None
    for m in MODULES:
        if any(x in (rm.url_name or "") for x in m.get("match", ())):
            return m["key"]
    return next((m["key"] for m in MODULES if rm.app_name in m.get("apps", ())), None)


def visible_modules(user):
    """US-019: moduły, do których rola ma dostęp — Podgląd nie widzi modułów tylko dla Projektanta."""
    designer = has_role(user, GROUP_ADMIN, GROUP_DESIGNER)
    admin = has_role(user, GROUP_ADMIN)
    return [m for m in MODULES if (designer or not m.get("designer")) and (admin or not m.get("admin"))]


def home(request):
    if not request.user.is_authenticated and settings.DEMO_PUBLIC:
        return redirect("core:demo")              # publiczne demo: gość zaczyna od strony wejściowej, nie od logowania
    return _home(request)


@login_required
def _home(request):
    modules = [{**m, "url": reverse(m["url"])} for m in visible_modules(request.user)]
    exposure = exposure_reasons() if settings.DEMO_PUBLIC and has_role(request.user, GROUP_ADMIN) else []
    return render(request, "core/home.html", {"modules": modules, "demo_exposure": exposure})


def demo(request):
    """Strona wejściowa publicznego demo (bez logowania): pokaz 3D, wejście gościa, film."""
    sc = demo_showcase()
    resp = render(request, "core/demo.html", {
        "showcase_url": reverse("scenario:public", args=[sc.share_token]) if sc else "",
        "guest": settings.DEMO_PUBLIC, "video_url": settings.DEMO_VIDEO_URL})
    resp["Referrer-Policy"] = "same-origin"       # adres pokazu niesie token — poza domenę go nie wysyłamy;
    # no-referrer odpada: przeglądarka wysłałaby wtedy Origin: null i CSRF odrzuciłby „Wejdź do systemu”
    return resp


@require_POST
def demo_enter(request):
    """Wejście gościa: sesja konta `demo` w roli Podgląd (tylko odczyt, bez danych źródłowych).
    Tylko z DEMO_PUBLIC; konto musi być zwykłym Podglądem — nigdy nie loguje kogoś z wyższymi prawami."""
    if not settings.DEMO_PUBLIC:
        raise Http404
    if not request.user.is_authenticated:
        user = User.objects.filter(username=DEMO_USER, is_active=True, is_staff=False, is_superuser=False,
                                   groups__name=GROUP_VIEWER).first()
        if user is None or user.groups.exclude(name=GROUP_VIEWER).exists():
            raise Http404
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("core:home")


AUDIT_PAGE = 200


@admin_only
def audit_log(request):
    """US-008: dziennik operacji wrażliwych — tylko Administrator; ostatnie wpisy, filtr po rodzaju."""
    action = request.GET.get("action", "")
    events = AuditEvent.objects.all()
    if action in dict(AuditEvent.ACTIONS):
        events = events.filter(action=action)
    else:
        action = ""
    return render(request, "core/audit_log.html", {
        "events": events[:AUDIT_PAGE], "actions": AuditEvent.ACTIONS, "action": action, "limit": AUDIT_PAGE,
        "retention_days": settings.AUDIT_RETENTION_DAYS})


@never_cache
@any_role
def job_status(request, pk):
    """US-007: stan zadania z kolejki dla ekranu oczekiwania — bez wyniku i parametrów."""
    job = get_object_or_404(Job, pk=pk)
    return JsonResponse({"status": job.status, "status_display": job.get_status_display(), "pending": job.pending})
