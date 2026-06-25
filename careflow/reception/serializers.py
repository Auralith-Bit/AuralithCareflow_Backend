from rest_framework import serializers
from .models import Patient, QueueEntry, ActivityLog


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'


class QueueEntrySerializer(serializers.ModelSerializer):
    time = serializers.TimeField(format='%I:%M %p')
    cancelled_at = serializers.TimeField(format='%I:%M %p', allow_null=True, required=False)

    class Meta:
        model = QueueEntry
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'token']


class QueueEntryCreateSerializer(serializers.Serializer):
    patient_name = serializers.CharField(max_length=200)
    patient_phone = serializers.CharField(max_length=20)
    doctor_id = serializers.IntegerField()
    visit_type = serializers.CharField(max_length=20, default='Walk-In')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    reuse_slot_id = serializers.IntegerField(required=False, allow_null=True)


class QueueEntryStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['waiting', 'arrived', 'serving', 'done'])


class QueueEntryCancelSerializer(serializers.Serializer):
    cancel_source = serializers.ChoiceField(choices=['patient-app', 'receptionist'], default='receptionist')


class QueueEntryRescheduleSerializer(serializers.Serializer):
    new_date = serializers.DateField()
    new_doctor_id = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = '__all__'
        read_only_fields = ['timestamp']
