"""US-022: nazwa własnego modelu sprzętu jest unikalna.

Przed założeniem ograniczenia powtórzone nazwy dostają przyrostek („Reach 1,6 t 2”) — najstarszy model
zachowuje nazwę. Zmiana nazwy nie zmienia parametrów ani powiązań (flota scenariuszy, regały).
"""

from django.db import migrations, models


def rename_duplicates(apps, schema_editor):
    Equipment = apps.get_model("equipment", "Equipment")
    taken = set(Equipment.objects.values_list("name", flat=True))
    seen = set()
    for eq in Equipment.objects.filter(is_system=False).order_by("created_at", "pk"):
        if eq.name not in seen:
            seen.add(eq.name)
            continue
        base, n = eq.name[:110], 2
        while f"{base} {n}" in taken:
            n += 1
        eq.name = f"{base} {n}"
        taken.add(eq.name)
        seen.add(eq.name)
        eq.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("equipment", "0006_klasy_rynkowe"),
    ]

    operations = [
        migrations.RunPython(rename_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="equipment",
            constraint=models.UniqueConstraint(condition=models.Q(("is_system", False)), fields=("name",),
                                               name="equipment_own_name_unique"),
        ),
    ]
