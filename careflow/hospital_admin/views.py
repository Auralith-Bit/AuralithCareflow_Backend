from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from accounts.permissions import IsHospitalAdmin
from rest_framework.permissions import IsAuthenticated
from .models import Department, Doctor, HospitalProfile, Holiday, TimeSlot, EmergencyClosure
from .serializers import (
    DepartmentSerializer, DoctorSerializer, DoctorListSerializer,
    HospitalProfileSerializer, HolidaySerializer, TimeSlotSerializer,
    EmergencyClosureSerializer,
)


@login_required
def admin_dashboard(request):
    return render(request, 'hospital-admin.html')


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.filter(is_active=True)
    serializer_class = DepartmentSerializer
    search_fields = ['name']
    ordering_fields = ['name']
    permission_classes = [IsHospitalAdmin]


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.filter(is_active=True)
    search_fields = ['name', 'specialty', 'department__name']
    ordering_fields = ['name', 'status']
    permission_classes = [IsHospitalAdmin]

    def get_serializer_class(self):
        if self.action == 'list':
            return DoctorListSerializer
        return DoctorSerializer


class HospitalProfileView(generics.RetrieveUpdateAPIView):
    queryset = HospitalProfile.objects.all()
    serializer_class = HospitalProfileSerializer
    permission_classes = [IsHospitalAdmin]

    def get_object(self):
        return HospitalProfile.get_profile()


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.filter(is_active=True)
    serializer_class = HolidaySerializer
    ordering_fields = ['date']
    ordering = ['date']
    permission_classes = [IsHospitalAdmin]

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsHospitalAdmin]

    def get_queryset(self):
        qs = TimeSlot.objects.all()
        doctor_id = self.request.query_params.get('doctor')
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        return qs


class EmergencyClosureViewSet(viewsets.ModelViewSet):
    queryset = EmergencyClosure.objects.filter(is_active=True)
    serializer_class = EmergencyClosureSerializer
    permission_classes = [IsHospitalAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
