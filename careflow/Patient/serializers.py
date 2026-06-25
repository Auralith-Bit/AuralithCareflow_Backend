from rest_framework import serializers
from .models import PatientProfile, FamilyMember, Appointment, DoctorReview, NotificationLog


class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = ['id', 'name', 'relationship', 'phone', 'date_of_birth', 'blood_group', 'is_active']


class PatientProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.name', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    family_members = FamilyMemberSerializer(many=True, read_only=True)

    class Meta:
        model = PatientProfile
        fields = ['id', 'name', 'phone', 'email', 'date_of_birth',
                  'blood_group', 'address', 'family_members',
                  'created_at', 'updated_at']


class PatientProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ['date_of_birth', 'blood_group', 'address']


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class AppointmentCreateSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField()
    doctor_name = serializers.CharField(max_length=200)
    doctor_specialty = serializers.CharField(required=False, allow_blank=True, default='')
    department_name = serializers.CharField(max_length=100)
    location = serializers.CharField(required=False, allow_blank=True, default='')
    appointment_date = serializers.DateField()
    appointment_time = serializers.TimeField()
    fee = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    patient_name = serializers.CharField(required=False, allow_blank=True, default='')
    patient_phone = serializers.CharField(required=False, allow_blank=True, default='')
    payment_method = serializers.CharField(required=False, allow_blank=True, default='')

    def create(self, validated_data):
        from .models import Appointment
        # Remove fields not on the Appointment model
        validated_data.pop('doctor_id', None)
        validated_data.pop('patient_name', None)
        validated_data.pop('patient_phone', None)
        validated_data.pop('payment_method', None)
        return Appointment.objects.create(**validated_data)


class DoctorReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.name', read_only=True)

    class Meta:
        model = DoctorReview
        fields = ['id', 'doctor', 'appointment', 'rating', 'comment', 'patient_name', 'created_at']
        read_only_fields = ['patient', 'created_at']


class DoctorReviewCreateSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()
    rating = serializers.ChoiceField(choices=[1, 2, 3, 4, 5])
    comment = serializers.CharField(required=False, allow_blank=True, default='')


class NotificationLogSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = NotificationLog
        fields = ['id', 'type', 'type_display', 'title', 'message', 'is_read', 'created_at']
        read_only_fields = ['patient', 'created_at']


class GuestBookingSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    doctor_id = serializers.IntegerField()
    appointment_date = serializers.DateField()
    appointment_time = serializers.TimeField()
    patient_name = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
