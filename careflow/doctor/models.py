from django.db import models
from django.utils import timezone
from hospital_admin.models import Doctor
from reception.models import QueueEntry


class VitalRecord(models.Model):
    queue_entry = models.ForeignKey(
        QueueEntry, on_delete=models.CASCADE, related_name='vital_records'
    )
    bp = models.CharField(max_length=20, blank=True, default='')
    pulse = models.IntegerField(null=True, blank=True)
    temp = models.FloatField(null=True, blank=True)
    spo2 = models.IntegerField(null=True, blank=True)
    weight = models.FloatField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    rbs = models.IntegerField(null=True, blank=True, verbose_name='RBS / Blood sugar (mg/dL)')
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    @property
    def bmi(self):
        if self.weight and self.height:
            return round(self.weight / ((self.height / 100) ** 2), 1)
        return None

    def __str__(self):
        return f"Vitals for {self.queue_entry.token} @ {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"


class ConsultationNote(models.Model):
    queue_entry = models.OneToOneField(
        QueueEntry, on_delete=models.CASCADE, related_name='consultation_note'
    )
    diagnosis = models.TextField(blank=True, default='')
    prescription = models.TextField(blank=True, default='')
    is_visible_to_patient = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Note for {self.queue_entry.token}"


class DoctorNotification(models.Model):
    doctor = models.ForeignKey(
        Doctor, on_delete=models.CASCADE, related_name='notifications'
    )
    type = models.CharField(max_length=30, default='info')
    icon = models.CharField(max_length=50, blank=True, default='ti-info-circle')
    icon_class = models.CharField(max_length=30, blank=True, default='ni-blue')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] {self.message[:50]}"


class DoctorScheduleSettings(models.Model):
    doctor = models.OneToOneField(
        Doctor, on_delete=models.CASCADE, related_name='schedule_settings'
    )
    slot_duration = models.IntegerField(default=10, help_text='Minutes per consultation slot')
    start_time = models.TimeField(default=timezone.datetime.strptime('09:00', '%H:%M').time())
    end_time = models.TimeField(default=timezone.datetime.strptime('17:00', '%H:%M').time())
    break_time = models.TimeField(default=timezone.datetime.strptime('13:00', '%H:%M').time(), null=True, blank=True)
    auto_advance = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Schedule: {self.doctor.name}"
