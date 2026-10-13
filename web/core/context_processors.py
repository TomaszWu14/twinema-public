from django.conf import settings

from .demo import DEMO_USER
from .roles import GROUP_ADMIN, GROUP_DESIGNER


def branding(request):
    user = getattr(request, "user", None)
    return {"app_name": settings.APP_NAME, "demo_public": settings.DEMO_PUBLIC,
            "is_demo_guest": bool(user and user.is_authenticated and user.get_username() == DEMO_USER)}


def user_roles(request):
    """Flagi ról do szablonów — jedno zapytanie zamiast wielu has_role()."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"is_admin": False, "is_designer": False}
    if user.is_superuser:
        return {"is_admin": True, "is_designer": True}
    names = set(user.groups.values_list("name", flat=True))
    is_admin = GROUP_ADMIN in names
    return {"is_admin": is_admin, "is_designer": is_admin or GROUP_DESIGNER in names}


def navigation(request):
    """Nawigacja w nagłówku z `core.views.MODULES` (te same nazwy co kafle strony głównej) + aktywna pozycja."""
    from django.urls import reverse

    from .views import MODULES, active_module
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    active = active_module(getattr(request, "resolver_match", None))
    return {"nav_modules": [{"name": m["name"], "url": reverse(m["url"]), "active": m["key"] == active}
                            for m in MODULES]}
