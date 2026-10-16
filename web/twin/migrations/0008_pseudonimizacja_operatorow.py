"""US-012 (RODO, R-06, decyzja PO): loginy operatorów w już zaimportowanych zadaniach → pseudonimy „OP-…”.
Ta sama funkcja co `twin.ewm_tasks.pseudonym` z kluczem `twin.shared.operator_key` (skopiowane — migracja nie
importuje kodu aplikacji). Operacji nie da się odwrócić: oryginalne loginy znikają z bazy."""
import hashlib
import hmac

from django.conf import settings
from django.db import migrations


def _key():
    return hashlib.sha256(b"twinema.operator-pseudonym:" + settings.SECRET_KEY.encode()).digest()


def _pseudonym(login, key):
    digest = hmac.new(key, login.strip().upper().encode(), hashlib.sha256).hexdigest()
    return "OP-" + digest[:10].upper()


def pseudonymize(apps, schema_editor):
    task = apps.get_model("twin", "WarehouseTask")
    key = _key()
    logins = task.objects.exclude(user="").exclude(user__startswith="OP-").values_list("user", flat=True).distinct()
    for login in list(logins):
        task.objects.filter(user=login).update(user=_pseudonym(login, key))


class Migration(migrations.Migration):
    dependencies = [("twin", "0007_kolory_domyslne_elementow")]
    operations = [migrations.RunPython(pseudonymize, migrations.RunPython.noop)]
