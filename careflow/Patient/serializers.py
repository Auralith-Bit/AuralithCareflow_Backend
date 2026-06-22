from rest_framework import serializers
from .models import PatientProfile, FamilyMember, Appointment


class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = ['id', 'name', 'relationship', 'phone', 'date_of_birth', 'blood_group', 'is_active']


class PatientProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    family_members = FamilyMemberSerializer(many=True, read_only=True)

    class Meta:
        model = PatientProfile
        fields = ['id', 'first_name', 'last_name', 'phone', 'email', 'date_of_birth',
                  'blood_group', 'address', 'emergency_contact', 'family_members',
                  'created_at', 'updated_at']


class PatientProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ['date_of_birth', 'blood_group', 'address', 'emergency_contact']


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
    fee = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    patient_name = serializers.CharField(required=False, allow_blank=True, default='')
    patient_phone = serializers.CharField(required=False, allow_blank=True, default='')
    payment_method = serializers.CharField(required=False, allow_blank=True, default='')
