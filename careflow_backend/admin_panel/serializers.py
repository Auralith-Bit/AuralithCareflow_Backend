from rest_framework import serializers
from .models import Department, Doctor, HospitalProfile, Holiday, TimeSlot, EmergencyClosure


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'


class DoctorSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)

    class Meta:
        model = Doctor
        fields = '__all__'


class DoctorListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)

    class Meta:
        model = Doctor
        fields = ['id', 'name', 'specialty', 'department_name', 'qualification', 'prefix',
                  'status', 'slots_per_day', 'avatar_color', 'days_available',
                  'morning_slots', 'evening_slots']


class HospitalProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalProfile
        fields = '__all__'


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = '__all__'


class EmergencyClosureSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyClosure
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at']
