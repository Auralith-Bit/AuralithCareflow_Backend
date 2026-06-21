from django.db import models
from accounts.models import User


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=10, default='🏥')
    floor = models.CharField(max_length=100, blank=True)
    head = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    doctors_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Doctor(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ON_LEAVE = 'on-leave', 'On Leave'

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctor_profile')
    name = models.CharField(max_length=200)
    specialty = models.CharField(max_length=200, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctors')
    qualification = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    avatar_color = models.CharField(max_length=20, default='av-1')
    days_available = models.CharField(max_length=100, default='Mon–Fri')
    morning_slots = models.CharField(max_length=100, blank=True, help_text="e.g. 09:00–13:00")
    evening_slots = models.CharField(max_length=100, blank=True, help_text="e.g. 17:00–19:00")
    slots_per_day = models.IntegerField(default=20)
    prefix = models.CharField(max_length=5, unique=True, help_text="Token prefix e.g. A, B, C")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class HospitalProfile(models.Model):
    name = models.CharField(max_length=200, default='City Care Medical Centre')
    address = models.TextField(blank=True, default='123, Health Nagar, Sector 7, Lucknow, UP — 226001')
    phone = models.CharField(max_length=50, blank=True, default='+91 98765 43210')
    email = models.EmailField(blank=True, default='admin@citycaremc.com')
    website = models.CharField(max_length=200, blank=True, default='www.citycaremc.com')
    logo_icon = models.CharField(max_length=10, default='🏥')
    registration_no = models.CharField(max_length=100, blank=True, default='#UPCM-2019-00427')
    established = models.IntegerField(blank=True, null=True, default=2019)
    bed_capacity = models.IntegerField(blank=True, null=True, default=120)
    accreditation = models.CharField(max_length=200, blank=True, default='NABH Certified')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hospital Profile'
        verbose_name_plural = 'Hospital Profile'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_profile(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.name


class Holiday(models.Model):
    class Type(models.TextChoices):
        NATIONAL = 'National Holiday', 'National Holiday'
        STATE = 'State Holiday', 'State Holiday'
        CLOSURE = 'Hospital Closure', 'Hospital Closure'
        MAINTENANCE = 'Maintenance', 'Maintenance'

    name = models.CharField(max_length=200)
    date = models.DateField()
    type = models.CharField(max_length=50, choices=Type.choices, default=Type.NATIONAL)
    affects_all = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"{self.name} ({self.date})"


class TimeSlot(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='time_slots')
    day_of_week = models.IntegerField(choices=[
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)
    max_patients = models.IntegerField(default=1)

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.doctor.name} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class EmergencyClosure(models.Model):
    reason = models.CharField(max_length=500)
    from_date = models.DateTimeField()
    to_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Emergency: {self.reason[:50]}"
