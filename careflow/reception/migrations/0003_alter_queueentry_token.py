from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reception', '0002_fix_duplicate_tokens'),
    ]

    operations = [
        migrations.AlterField(
            model_name='queueentry',
            name='token',
            field=models.CharField(db_index=True, max_length=20, unique=True),
        ),
    ]
