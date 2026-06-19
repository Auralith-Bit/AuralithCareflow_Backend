from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = 'patient', 'Patient'
        DOCTOR = 'doctor', 'Doctor'
        RECEPTIONIST = 'receptionist', 'Receptionist'
        HOSPITAL_ADMIN = 'hospital_admin', 'Hospital Admin'
        SUPER_ADMIN = 'super_admin', 'Super Admin'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RECEPTIONIST)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    avatar_color = models.CharField(max_length=20, blank=True, default='av-1')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
