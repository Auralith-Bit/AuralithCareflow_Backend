from django.contrib import admin
from .models import Department, Doctor, HospitalProfile, Holiday, TimeSlot, EmergencyClosure

admin.site.register(Department)
admin.site.register(Doctor)
admin.site.register(HospitalProfile)
admin.site.register(Holiday)
admin.site.register(TimeSlot)
admin.site.register(EmergencyClosure)
