"""Film bez lektora: znika nagranie (VoiceTrack), głos prezentacji i etap „Lektor”.
Prezentacje w etapie „Lektor” wracają do „Tekst zatwierdzony” — render i montaż liczą długość ujęć z tekstu.
Pliki MP3 starych nagrań zostają w MEDIA_ROOT/voice/ (do ręcznego usunięcia)."""
from django.db import migrations, models


def audio_to_approved(apps, schema_editor):
    apps.get_model("studio", "Presentation").objects.filter(status="audio").update(status="approved")


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0004_kadry'),
    ]

    operations = [
        migrations.RunPython(audio_to_approved, migrations.RunPython.noop),
        migrations.RemoveField(model_name='shot', name='voice'),
        migrations.RemoveField(model_name='presentation', name='voice_id'),
        migrations.DeleteModel(name='VoiceTrack'),
        migrations.AlterField(
            model_name='presentation',
            name='status',
            field=models.CharField(choices=[('draft', 'Szkic'), ('approved', 'Tekst zatwierdzony'),
                                            ('render', 'Render ujęć'), ('montage', 'Montaż'), ('done', 'Gotowe')],
                                   db_index=True, default='draft', max_length=8),
        ),
        migrations.AlterField(
            model_name='shot',
            name='text',
            field=models.TextField(verbose_name='Tekst na ekranie'),
        ),
    ]
