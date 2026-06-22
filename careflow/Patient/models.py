from django.db import models
from accounts.models import User


class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, blank=True, default='')
    address = models.TextField(blank=True, default='')
    emergency_contact = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


class FamilyMember(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='family_members')
    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.relationship})"


class Appointment(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmed'
        SCHEDULED = 'scheduled', 'Scheduled'
        RESCHEDULED = 'rescheduled', 'Rescheduled'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'
        MISSED = 'missed', 'Missed'

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='appointments')
    doctor_name = models.CharField(max_length=200)
    doctor_specialty = models.CharField(max_length=200, blank=True)
    department_name = models.CharField(max_length=100)
    location = models.CharField(max_length=200, blank=True)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    token = models.CharField(max_length=20, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-appointment_date', '-appointment_time']

    def __str__(self):
        return f"{self.token} - {self.doctor_name} @ {self.appointment_date}"
