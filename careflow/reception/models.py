from django.db import models
from django.utils import timezone
from accounts.models import User
from hospital_admin.models import Doctor


class Patient(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.phone})"


class QueueEntry(models.Model):
    class VisitType(models.TextChoices):
        WALK_IN = 'Walk-In', 'Walk-In'
        BOOKING = 'Booking', 'Booking'
        EMERGENCY = 'Emergency', 'Emergency'
        FOLLOW_UP = 'Follow-Up', 'Follow-Up'

    class Status(models.TextChoices):
        WAITING = 'waiting', 'Waiting'
        ARRIVED = 'arrived', 'Arrived'
        SERVING = 'serving', 'Serving'
        DONE = 'done', 'Done'
        CANCELLED = 'cancelled', 'Cancelled'

    class CancelSource(models.TextChoices):
        PATIENT_APP = 'patient-app', 'Cancelled by Patient (App)'
        RECEPTIONIST = 'receptionist', 'Cancelled by Receptionist'

    token = models.CharField(max_length=20, db_index=True)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name='queue_entries')
    patient_name = models.CharField(max_length=200)
    patient_phone = models.CharField(max_length=20)
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='queue_entries')
    doctor_name = models.CharField(max_length=200)
    department_name = models.CharField(max_length=100)
    room = models.CharField(max_length=50, blank=True, default='')
    visit_type = models.CharField(max_length=20, choices=VisitType.choices, default=VisitType.WALK_IN)
    time = models.TimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    notes = models.TextField(blank=True, default='')
    cancelled_at = models.TimeField(null=True, blank=True)
    cancel_source = models.CharField(max_length=20, choices=CancelSource.choices, null=True, blank=True)
    reassigned = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['time']
        verbose_name_plural = 'Queue Entries'

    def __str__(self):
        return f"{self.token} - {self.patient_name}"


class ActivityLog(models.Model):
    class Type(models.TextChoices):
        CANCEL = 'cancel', 'Cancel'
        CHECKIN = 'checkin', 'Check-In'
        ISSUE = 'issue', 'Token Issue'
        RECEPTION = 'reception', 'Reception Action'

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.CHECKIN)
    related_token = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.type}] {self.message[:50]}"


class TokenCounter(models.Model):
    doctor_prefix = models.CharField(max_length=5, db_index=True)
    date = models.DateField(default=timezone.now)
    counter_value = models.IntegerField(default=0)

    class Meta:
        unique_together = ['doctor_prefix', 'date']

    def __str__(self):
        return f"{self.doctor_prefix}-{self.counter_value} ({self.date})"

    @classmethod
    def get_next_token(cls, prefix):
        today = timezone.now().date()
        counter, _ = cls.objects.get_or_create(doctor_prefix=prefix, date=today)
        counter.counter_value += 1
        counter.save()
        return f"{prefix}-{counter.counter_value}"
