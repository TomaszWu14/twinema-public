"""Uzupełnienie 0008 (przegląd kodu, US-012, RODO): 0008 pomijała każdy login zaczynający się od „OP-”, więc loginy
systemu magazynowego w rodzaju „OP-0001” zostały jawne w starych importach, a nowe importy je pseudonimizują.
Tu pomijamy tylko dokładny format pseudonimu: „OP-” i 10 znaków szesnastkowych. Funkcja jak w 0008 (kopia —
migracja nie importuje kodu aplikacji). Operacji nie da się odwrócić."""
import hashlib
import hmac
import re

from django.conf import settings
from django.db import migrations

PSEUDONYM = re.compile(r"^OP-[0-9A-F]{10}$")


def _key():
    return hashlib.sha256(b"twinema.operator-pseudonym:" + settings.SECRET_KEY.encode()).digest()


def _pseudonym(login, key):
    digest = hmac.new(key, login.strip().upper().encode(), hashlib.sha256).hexdigest()
    return "OP-" + digest[:10].upper()


def pseudonymize(apps, schema_editor):
    task = apps.get_model("twin", "WarehouseTask")
    key = _key()
    logins = task.objects.filter(user__startswith="OP-").values_list("user", flat=True).distinct()
    for login in [x for x in logins if not PSEUDONYM.match(x)]:
        task.objects.filter(user=login).update(user=_pseudonym(login, key))


class Migration(migrations.Migration):
    dependencies = [("twin", "0008_pseudonimizacja_operatorow")]
    operations = [migrations.RunPython(pseudonymize, migrations.RunPython.noop)]
