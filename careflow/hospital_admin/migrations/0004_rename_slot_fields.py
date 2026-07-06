from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hospital_admin', '0003_doctor_disabled_slots'),
    ]

    operations = [
        migrations.RenameField(
            model_name='doctor',
            old_name='morning_slots',
            new_name='day_slots',
        ),
        migrations.RenameField(
            model_name='doctor',
            old_name='evening_slots',
            new_name='night_slots',
        ),
    ]
