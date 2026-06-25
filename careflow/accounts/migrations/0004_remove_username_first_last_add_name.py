from django.db import migrations, models


def copy_name(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():
        name = f"{user.first_name} {user.last_name}".strip()
        if not name:
            name = user.phone or 'Unknown'
        user.name = name
        user.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_user_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='name',
            field=models.CharField(max_length=300, null=True, blank=True),
        ),
        migrations.RunPython(copy_name),
        migrations.RemoveField(
            model_name='user',
            name='username',
        ),
        migrations.RemoveField(
            model_name='user',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='user',
            name='last_name',
        ),
        migrations.AlterField(
            model_name='user',
            name='name',
            field=models.CharField(max_length=300),
        ),
    ]
