from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, phone, name, password=None, **extra_fields):
        if not phone:
            raise ValueError('Phone is required')
        user = self.model(phone=phone, name=name, **extra_fields)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        PATIENT = 'patient', 'Patient'
        DOCTOR = 'doctor', 'Doctor'
        RECEPTIONIST = 'receptionist', 'Receptionist'
        HOSPITAL_ADMIN = 'hospital_admin', 'Hospital Admin'
        SUPER_ADMIN = 'super_admin', 'Super Admin'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=300)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    email = models.EmailField(blank=True, default='')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    avatar_color = models.CharField(max_length=20, blank=True, default='av-1')
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True, default='')
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, default='info')
    title = models.CharField(max_length=200, blank=True, default='')
    message = models.TextField()
    icon = models.CharField(max_length=50, blank=True, default='ti-info-circle')
    icon_color = models.CharField(max_length=30, blank=True, default='ni-blue')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] {self.message[:50]}"

    @classmethod
    def send(cls, user, type, message, title='', icon='ti-info-circle', icon_color='ni-blue'):
        qs = cls.objects.filter(user=user)
        if qs.count() >= 50:
            oldest = qs.order_by('created_at')[:qs.count() - 50]
            cls.objects.filter(pk__in=[o.pk for o in oldest]).delete()
        return cls.objects.create(
            user=user, type=type, title=title,
            message=message, icon=icon, icon_color=icon_color,
        )
