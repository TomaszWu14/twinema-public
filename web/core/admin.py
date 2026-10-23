from django.contrib import admin

from .models import DemoVisitor
from .roles import GROUP_ADMIN, has_role


@admin.register(DemoVisitor)
class DemoVisitorAdmin(admin.ModelAdmin):
    """Lista odwiedzających demo (RODO CP-7) — tylko do odczytu, tylko Administrator; najnowsi na górze."""

    list_display = ("created_at", "first_name", "last_name", "company", "ekrany", "czas", "najczesciej")
    search_fields = ("first_name", "last_name", "company")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(description="Ekrany", ordering="page_views")
    def ekrany(self, obj):
        return obj.page_views

    @admin.display(description="Czas")
    def czas(self, obj):
        minutes = obj.duration_minutes()
        return "—" if minutes is None else f"ok. {minutes} min"

    @admin.display(description="Najczęściej")
    def najczesciej(self, obj):
        return ", ".join(obj.top_sections()) or "—"

    def _admin_only(self, request, obj=None):
        return request.user.is_active and request.user.is_staff and (
            request.user.is_superuser or has_role(request.user, GROUP_ADMIN))

    has_module_permission = has_view_permission = _admin_only

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return self._admin_only(request)          # usunięcie na żądanie osoby (RODO art. 17)
