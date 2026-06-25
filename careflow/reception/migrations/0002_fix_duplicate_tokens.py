from django.db import migrations, models
from django.db.models import Max


def fix_duplicate_tokens(apps, schema_editor):
    QueueEntry = apps.get_model('reception', 'QueueEntry')
    TokenCounter = apps.get_model('reception', 'TokenCounter')
    from django.utils import timezone

    all_entries = QueueEntry.objects.all().order_by('created_at')
    seen_tokens = set()
    today = timezone.now().date()

    for entry in all_entries:
        if entry.token in seen_tokens:
            prefix = entry.token.split('-')[0]
            max_val = TokenCounter.objects.filter(
                doctor_prefix=prefix
            ).aggregate(max_val=Max('counter_value'))['max_val'] or 0
            new_counter = max_val + 1
            TokenCounter.objects.update_or_create(
                doctor_prefix=prefix,
                date=today,
                defaults={'counter_value': new_counter},
            )
            new_token = f"{prefix}-{new_counter}"
            QueueEntry.objects.filter(pk=entry.pk).update(token=new_token)
            seen_tokens.add(new_token)
        else:
            seen_tokens.add(entry.token)


class Migration(migrations.Migration):

    dependencies = [
        ('reception', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fix_duplicate_tokens),
    ]
