from datetime import date, time, datetime
from django.db.models import Q, Count
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsReceptionist
from hospital_admin.models import Doctor
from .models import Patient, QueueEntry, ActivityLog, TokenCounter
from .serializers import (
    PatientSerializer, QueueEntrySerializer,
    QueueEntryCreateSerializer, QueueEntryStatusSerializer,
    QueueEntryCancelSerializer, QueueEntryRescheduleSerializer,
    ActivityLogSerializer,
)


@login_required
def reception_dashboard(request):
    return render(request, 'reception.html')


class QueueListView(generics.ListAPIView):
    serializer_class = QueueEntrySerializer
    permission_classes = [IsReceptionist]

    def get_queryset(self):
        qs = QueueEntry.objects.all()
        status_filter = self.request.query_params.get('status')
        visit_type = self.request.query_params.get('type')
        reassigned = self.request.query_params.get('reassigned')

        if status_filter:
            if status_filter == 'available':
                qs = qs.filter(status='cancelled', reassigned=False)
            else:
                qs = qs.filter(status=status_filter)
        if visit_type:
            types = visit_type.split(',')
            qs = qs.filter(visit_type__in=types)
        if reassigned is not None:
            qs = qs.filter(reassigned=reassigned.lower() == 'true')

        return qs.order_by('time')


class QueueStatsView(APIView):
    permission_classes = [IsReceptionist]

    def get(self, request):
        qs = QueueEntry.objects.all()
        return Response({
            'total': qs.count(),
            'waiting': qs.filter(status='waiting').count(),
            'arrived': qs.filter(status='arrived').count(),
            'serving': qs.filter(status='serving').count(),
            'cancelled': qs.filter(status='cancelled').count(),
            'done': qs.filter(status='done').count(),
            'available': qs.filter(status='cancelled', reassigned=False).count(),
        })


class QueueDetailView(generics.RetrieveAPIView):
    queryset = QueueEntry.objects.all()
    serializer_class = QueueEntrySerializer
    permission_classes = [IsReceptionist]


class CreateQueueEntryView(APIView):
    permission_classes = [IsReceptionist]

    def post(self, request):
        serializer = QueueEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        reuse_slot_id = data.get('reuse_slot_id')

        if reuse_slot_id:
            entry = get_object_or_404(QueueEntry, id=reuse_slot_id)
            if entry.status != 'cancelled' or entry.reassigned:
                return Response(
                    {'error': 'This slot is no longer available for reassignment.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            entry.patient_name = data['patient_name']
            entry.patient_phone = data['patient_phone']
            entry.visit_type = data['visit_type']
            entry.status = 'waiting'
            entry.reassigned = True
            entry.notes = data.get('notes', '')
            entry.save()
            ActivityLog.objects.create(
                user=request.user,
                type=ActivityLog.Type.ISSUE,
                message=f"Cancelled slot {entry.token} reassigned to walk-in: {data['patient_name']}",
                related_token=entry.token,
            )
            return Response(QueueEntrySerializer(entry).data)

        doctor = get_object_or_404(Doctor, id=data['doctor_id'])
        token = TokenCounter.get_next_token(doctor.prefix)
        now = timezone.now()

        entry = QueueEntry.objects.create(
            token=token,
            patient_name=data['patient_name'],
            patient_phone=data['patient_phone'],
            doctor=doctor,
            doctor_name=doctor.name,
            department_name=doctor.department.name if doctor.department else '',
            room='',
            visit_type=data['visit_type'],
            time=now.time(),
            status='waiting',
            notes=data.get('notes', ''),
            created_by=request.user,
        )
        ActivityLog.objects.create(
            user=request.user,
            type=ActivityLog.Type.ISSUE,
            message=f"Walk-in token {token} issued to {data['patient_name']}",
            related_token=token,
        )
        return Response(QueueEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class UpdateQueueStatusView(APIView):
    permission_classes = [IsReceptionist]

    def patch(self, request, pk):
        entry = QueueEntry.objects.get(pk=pk)
        serializer = QueueEntryStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry.status = serializer.validated_data['status']
        entry.save()
        ActivityLog.objects.create(
            user=request.user,
            type=ActivityLog.Type.CHECKIN,
            message=f"{entry.token} — {entry.patient_name} marked as {entry.get_status_display()}",
            related_token=entry.token,
        )
        return Response(QueueEntrySerializer(entry).data)


class CancelQueueEntryView(APIView):
    permission_classes = [IsReceptionist]

    def patch(self, request, pk):
        entry = QueueEntry.objects.get(pk=pk)
        serializer = QueueEntryCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        entry.status = 'cancelled'
        entry.cancelled_at = now.time()
        entry.cancel_source = serializer.validated_data['cancel_source']
        entry.reassigned = False
        entry.save()
        ActivityLog.objects.create(
            user=request.user,
            type=ActivityLog.Type.CANCEL,
            message=f"Token {entry.token} cancelled — {entry.patient_name}. Slot now available.",
            related_token=entry.token,
        )
        return Response(QueueEntrySerializer(entry).data)


class RescheduleQueueEntryView(APIView):
    permission_classes = [IsReceptionist]

    def patch(self, request, pk):
        entry = QueueEntry.objects.get(pk=pk)
        serializer = QueueEntryRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        entry.status = 'done'
        entry.notes = f"Rescheduled to {data['new_date']}. {data.get('reason', '')}"
        entry.save()
        ActivityLog.objects.create(
            user=request.user,
            type=ActivityLog.Type.CHECKIN,
            message=f"Token {entry.token} rescheduled — {entry.patient_name} → {data['new_date']}",
            related_token=entry.token,
        )
        return Response(QueueEntrySerializer(entry).data)


class PatientSearchView(APIView):
    permission_classes = [IsReceptionist]

    def get(self, request):
        q = request.query_params.get('q', '').strip().lower()
        if not q:
            return Response([])
        search_type = request.query_params.get('type', 'all')
        qs = QueueEntry.objects.all()
        if search_type == 'name':
            qs = qs.filter(patient_name__icontains=q)
        elif search_type == 'phone':
            clean = q.replace('-', '').replace(' ', '').replace('+', '')
            qs = qs.filter(patient_phone__icontains=clean)
        elif search_type == 'token':
            qs = qs.filter(token__icontains=q)
        else:
            clean_phone = q.replace('-', '').replace(' ', '').replace('+', '')
            qs = qs.filter(
                Q(patient_name__icontains=q) |
                Q(patient_phone__icontains=clean_phone) |
                Q(token__icontains=q)
            )
        qs = qs.order_by('-created_at')[:20]
        return Response(QueueEntrySerializer(qs, many=True).data)


class CheckExistingPatientView(APIView):
    permission_classes = [IsReceptionist]

    def get(self, request):
        phone = request.query_params.get('phone', '').replace('-', '').replace(' ', '')
        if len(phone) < 10:
            return Response({'found': False})
        entry = QueueEntry.objects.filter(
            patient_phone__contains=phone
        ).exclude(status__in=['done', 'cancelled']).first()
        if entry:
            return Response({
                'found': True,
                'token': entry.token,
                'status': entry.status,
            })
        return Response({'found': False})


class NextTokenView(APIView):
    permission_classes = [IsReceptionist]

    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        if not doctor_id:
            return Response({'error': 'doctor_id required'}, status=400)
        doctor = Doctor.objects.get(id=doctor_id)
        today = timezone.now().date()
        counter, _ = TokenCounter.objects.get_or_create(doctor_prefix=doctor.prefix, date=today)
        next_num = counter.counter_value + 1
        return Response({'token': f"{doctor.prefix}-{next_num}", 'prefix': doctor.prefix})


class ActivityLogListView(generics.ListCreateAPIView):
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsReceptionist]

    def get_queryset(self):
        limit = self.request.query_params.get('limit')
        qs = ActivityLog.objects.all()
        if limit:
            qs = qs[:int(limit)]
        return qs


class DoctorListView(generics.ListAPIView):
    queryset = Doctor.objects.filter(is_active=True, status='active')
    serializer_class = None
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        doctors = Doctor.objects.filter(is_active=True)
        data = []
        for d in doctors:
            waiting = QueueEntry.objects.filter(doctor=d, status='waiting').count()
            data.append({
                'id': d.id,
                'name': d.name,
                'dept': d.department.name if d.department else '',
                'room': '',
                'prefix': d.prefix,
                'waiting_count': waiting,
            })
        return Response(data)
