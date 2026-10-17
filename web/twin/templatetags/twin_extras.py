"""Tagi szablonów modułu: ikony Lucide ze sprite'a static/twin/icons/lucide.svg."""
from django import template
from django.template import TemplateSyntaxError
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

ICON_SIZES = (16, 20, 24)


@register.simple_tag
def icon(name, size=16, label="", cls=""):
    """{% icon "package" %} → dekoracyjna (aria-hidden); z label → role=img + aria-label."""
    size = int(size)
    if size not in ICON_SIZES:
        raise TemplateSyntaxError(f"icon: rozmiar {size} spoza {ICON_SIZES}")
    href = f"{static('twin/icons/lucide.svg')}#{name}"
    # B308: mark_safe tylko na stałym atrybucie, bez danych wejściowych
    a11y = format_html('role="img" aria-label="{}"', label) if label else mark_safe('aria-hidden="true"')  # nosec B308
    return format_html(
        '<svg class="icon icon--{} {}" width="{}" height="{}" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" focusable="false" {}>'
        '<use href="{}"></use></svg>',
        size, cls, size, size, a11y, href,
    )
