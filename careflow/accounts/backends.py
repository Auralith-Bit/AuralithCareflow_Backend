from django.contrib.auth.backends import ModelBackend
from .models import User


class EmployeeIDBackend(ModelBackend):
    def authenticate(self, request, employee_id=None, password=None, **kwargs):
        if employee_id is None:
            employee_id = kwargs.get(User.USERNAME_FIELD)
        if employee_id is None or password is None:
            return None
        try:
            user = User.objects.get(employee_id=employee_id)
        except User.DoesNotExist:
            return None
        if user.check_password(password):
            return user
        return None
