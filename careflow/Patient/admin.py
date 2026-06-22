from django.contrib import admin
from .models import PatientProfile, FamilyMember, Appointment

admin.site.register(PatientProfile)
admin.site.register(FamilyMember)
admin.site.register(Appointment)
