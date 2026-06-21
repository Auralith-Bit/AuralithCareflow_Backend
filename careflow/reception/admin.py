from django.contrib import admin
from .models import Patient, QueueEntry, ActivityLog, TokenCounter

admin.site.register(Patient)
admin.site.register(QueueEntry)
admin.site.register(ActivityLog)
admin.site.register(TokenCounter)
