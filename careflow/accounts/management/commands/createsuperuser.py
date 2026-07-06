from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from getpass import getpass


class Command(BaseCommand):
    help = 'Create a super admin with Employee ID login'

    def handle(self, *args, **options):
        UserModel = get_user_model()
        verbosity = options.get('verbosity', 1)

        employee_id = input('Employee ID: ').strip()
        while not employee_id:
            self.stderr.write('Error: Employee ID is required.')
            employee_id = input('Employee ID: ').strip()
        while UserModel.objects.filter(employee_id=employee_id).exists():
            self.stderr.write('Error: Employee ID already exists.')
            employee_id = input('Employee ID: ').strip()

        name = input('Name: ').strip()
        while not name:
            self.stderr.write('Error: Name is required.')
            name = input('Name: ').strip()

        password = None
        while password is None:
            password = getpass('Password: ')
            if not password:
                self.stderr.write('Error: Password is required.')
                continue
            password2 = getpass('Password (again): ')
            if password != password2:
                self.stderr.write('Error: Passwords do not match.')
                password = None

        user = UserModel(
            name=name,
            employee_id=employee_id,
            role='super_admin',
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        user.set_password(password)
        user.save()

        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS(
                f'Super admin created successfully.\n'
                f'  Employee ID: {employee_id}\n'
                f'  Name: {name}'
            ))
