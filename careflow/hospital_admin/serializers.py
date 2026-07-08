from rest_framework import serializers
from .models import Department, Doctor, HospitalProfile, Holiday, TimeSlot, EmergencyClosure


class DepartmentSerializer(serializers.ModelSerializer):
    doctors_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = '__all__'

    def get_doctors_count(self, obj):
        count = obj.doctors.count()
        if obj.head:
            head_doc = Doctor.objects.filter(name=obj.head, is_active=True).exclude(department=obj).first()
            if head_doc:
                count += 1
        return count


class DoctorSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    employee_id = serializers.CharField(source='user.employee_id', read_only=True, allow_null=True)

    class Meta:
        model = Doctor
        fields = '__all__'


class DoctorListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    employee_id = serializers.CharField(source='user.employee_id', read_only=True, allow_null=True)

    class Meta:
        model = Doctor
        fields = ['id', 'name', 'specialty', 'department_name', 'qualification', 'prefix',
                  'status', 'slots_per_day', 'avatar_color', 'days_available',
                  'day_slots', 'night_slots', 'consultation_fee',
                  'phone', 'email', 'department', 'is_active', 'employee_id']


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
