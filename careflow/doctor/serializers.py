from rest_framework import serializers
from hospital_admin.models import Doctor
from reception.models import QueueEntry
from .models import VitalRecord, ConsultationNote, DoctorNotification, DoctorScheduleSettings


class DoctorProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)

    class Meta:
        model = Doctor
        fields = ['id', 'name', 'specialty', 'department_name', 'qualification',
                  'phone', 'email', 'prefix', 'status', 'avatar_color']


class DoctorProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ['name', 'phone', 'email', 'specialty']


class QueueEntrySerializer(serializers.ModelSerializer):
    age = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()
    complaint = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    vitals = serializers.SerializerMethodField()
    referred_to = serializers.SerializerMethodField()
    refer_reason = serializers.SerializerMethodField()

    class Meta:
        model = QueueEntry
        fields = ['id', 'token', 'patient_name', 'age', 'gender', 'patient_phone',
                  'complaint', 'status', 'note', 'vitals', 'visit_type', 'time',
                  'referred_to', 'refer_reason', 'doctor_name', 'department_name']

    def _get_from_notes(self, obj, key):
        if obj.notes:
            for part in obj.notes.split('|'):
                if ':' in part:
                    k, v = part.split(':', 1)
                    if k.strip() == key and v.strip():
                        return v.strip()
        return None

    def get_age(self, obj):
        age = self._get_from_notes(obj, 'age')
        return age if age else '—'

    def get_gender(self, obj):
        gender = self._get_from_notes(obj, 'gender')
        return gender if gender else '—'

    def get_complaint(self, obj):
        complaint = self._get_from_notes(obj, 'complaint')
        if complaint:
            return complaint
        return obj.notes.split('|')[0] if obj.notes else 'General consultation'

    def get_note(self, obj):
        try:
            cn = obj.consultation_note
            parts = []
            if cn.diagnosis:
                parts.append(cn.diagnosis)
            if cn.prescription:
                parts.append(cn.prescription)
            return ' | '.join(parts)
        except ConsultationNote.DoesNotExist:
            return ''

    def get_vitals(self, obj):
        vr = obj.vital_records.first()
        if vr:
            return {
                'bp': vr.bp,
                'pulse': vr.pulse,
                'temp': vr.temp,
                'spo2': vr.spo2,
                'weight': vr.weight,
                'height': vr.height,
                'rbs': vr.rbs,
                'bmi': vr.bmi,
            }
        return {}

    def get_referred_to(self, obj):
        return getattr(obj, '_referred_to', '')

    def get_refer_reason(self, obj):
        return getattr(obj, '_refer_reason', '')


class QueueStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    waiting = serializers.IntegerField()
    serving = serializers.IntegerField()
    done = serializers.IntegerField()
    skipped = serializers.IntegerField()
    noshow = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    est_time = serializers.CharField()


class VitalRecordSerializer(serializers.ModelSerializer):
    bmi = serializers.FloatField(read_only=True)

    class Meta:
        model = VitalRecord
        fields = ['id', 'queue_entry', 'bp', 'pulse', 'temp', 'spo2',
                  'weight', 'height', 'rbs', 'bmi', 'recorded_at']


class ConsultationNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultationNote
        fields = ['id', 'queue_entry', 'diagnosis', 'prescription',
                  'is_visible_to_patient', 'created_at', 'updated_at']


class DoctorNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorNotification
        fields = ['id', 'doctor', 'type', 'icon', 'icon_class',
                  'message', 'is_read', 'created_at']


class DoctorScheduleSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorScheduleSettings
        fields = ['id', 'doctor', 'slot_duration', 'start_time',
                  'end_time', 'break_time', 'auto_advance']


class ReferDoctorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    specialty = serializers.CharField()
    department_name = serializers.CharField()


class RegisterPatientSerializer(serializers.Serializer):
    patient_name = serializers.CharField(max_length=200)
    patient_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    complaint = serializers.CharField(required=False, allow_blank=True, default='')
    token_type = serializers.ChoiceField(choices=['normal', 'priority', 'emergency'], default='normal')
    age = serializers.IntegerField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True, default='')
    address = serializers.CharField(required=False, allow_blank=True, default='')
