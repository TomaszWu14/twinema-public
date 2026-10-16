"""Każdy formularz POST w szablonach ma token CSRF (US-014).

Zastępuje regułę semgrep `django-no-csrf-token`, która w trybie ogólnym zgłaszała
fałszywe alarmy dla długich formularzy z pętlami. Klient testowy Django nie sprawdza
CSRF, więc brak tokenu nie wyszedłby w testach widoków — dlatego kontrola szablonów.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

FORM_OPEN = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
POST = re.compile(r"""method\s*=\s*["']?post""", re.IGNORECASE)
FORM_CLOSE = re.compile(r"</form\s*>", re.IGNORECASE)


def post_forms_without_token(text):
    """Numery linii formularzy POST bez `{% csrf_token %}` przed `</form>`."""
    missing = []
    for m in FORM_OPEN.finditer(text):
        if not POST.search(m.group(0)):
            continue
        end = FORM_CLOSE.search(text, m.end())
        body = text[m.end():end.start() if end else len(text)]
        if "{% csrf_token %}" not in body:
            missing.append(text.count("\n", 0, m.start()) + 1)
    return missing


class PostFormsHaveCsrfTokenTests(SimpleTestCase):
    def test_detector_finds_missing_token(self):
        self.assertEqual(post_forms_without_token('<form method="post">\n</form>'), [1])
        self.assertEqual(post_forms_without_token('<form method="post">{% csrf_token %}</form>'), [])
        self.assertEqual(post_forms_without_token('<form method="get"></form>'), [])

    def test_every_post_form_in_templates_has_token(self):
        root = Path(settings.BASE_DIR)
        templates = [p for p in root.glob("*/templates/**/*.html")]
        self.assertGreater(len(templates), 50)
        problems = []
        for path in templates:
            for line in post_forms_without_token(path.read_text(encoding="utf-8")):
                problems.append(f"{path.relative_to(root)}:{line}")
        self.assertEqual(problems, [], "Formularze POST bez {% csrf_token %}")
