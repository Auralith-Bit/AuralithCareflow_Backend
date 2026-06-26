from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from accounts.models import User


GROUP_PERMISSIONS = {
    'Admin': {
        'roles': ['hospital_admin', 'super_admin'],
        'models': {
            'Department': ['view', 'add', 'change', 'delete'],
            'Doctor': ['view', 'add', 'change', 'delete'],
            'HospitalProfile': ['view', 'change'],
            'Holiday': ['view', 'add', 'change', 'delete'],
            'TimeSlot': ['view', 'add', 'change', 'delete'],
            'EmergencyClosure': ['view', 'add', 'change', 'delete'],
            'QueueEntry': ['view', 'add', 'change', 'delete'],
            'ActivityLog': ['view', 'add'],
            'TokenCounter': ['view', 'add', 'change'],
            'User': ['view', 'add', 'change', 'delete'],
            'Group': ['view', 'add', 'change', 'delete'],
            'Permission': ['view'],
            'Patient': ['view', 'add', 'change', 'delete'],
        },
    },
    'Doctor': {
        'roles': ['doctor'],
        'models': {
            'QueueEntry': ['view'],
            'Patient': ['view'],
            'Doctor': ['view'],
            'Department': ['view'],
        },
    },
    'Reception': {
        'roles': ['receptionist'],
        'models': {
            'QueueEntry': ['view', 'add', 'change'],
            'ActivityLog': ['view', 'add'],
            'TokenCounter': ['view', 'add', 'change'],
            'Patient': ['view', 'add', 'change'],
            'Doctor': ['view'],
            'Department': ['view'],
        },
    },
    'Patient': {
        'roles': ['patient'],
        'models': {
            'QueueEntry': ['view'],
            'Patient': ['view'],
        },
    },
}


class Command(BaseCommand):
    help = 'Create default groups with permissions and assign users by role'

    def handle(self, *args, **options):
        for group_name, config in GROUP_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(f"Created group '{group_name}'")
            else:
                self.stdout.write(f"Updating group '{group_name}'")

            perm_ids = []
            for model_name, actions in config['models'].items():
                for ct in ContentType.objects.all():
                    if ct.model == model_name.lower():
                        for action in actions:
                            codename = f"{action}_{model_name.lower()}"
                            try:
                                perm = Permission.objects.get(
                                    content_type=ct, codename=codename
                                )
                                perm_ids.append(perm.id)
                            except Permission.DoesNotExist:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"  Permission '{codename}' not found for {model_name}"
                                    )
                                )
                        break

            group.permissions.set(perm_ids)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Assigned {len(perm_ids)} permissions to '{group_name}'"
                )
            )

            roles = config.get('roles', [])
            users = User.objects.filter(role__in=roles)
            for user in users:
                user.groups.add(group)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Assigned {users.count()} users to '{group_name}'"
                )
            )

        self.stdout.write(self.style.SUCCESS("Done!"))
