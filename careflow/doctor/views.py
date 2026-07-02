from datetime import datetime, timedelta
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from accounts.decorators import role_required
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from hospital_admin.models import Doctor
from reception.models import QueueEntry, TokenCounter
from .permissions import IsDoctor
from .models import VitalRecord, ConsultationNote, DoctorNotification, DoctorScheduleSettings
from .serializers import (
    DoctorProfileSerializer, DoctorProfileUpdateSerializer,
    QueueEntrySerializer, VitalRecordSerializer,
    ConsultationNoteSerializer, DoctorNotificationSerializer,
    DoctorScheduleSettingsSerializer, RegisterPatientSerializer,
)


def _parse_notes_field(entry):
    extra = {}
    if entry.notes:
        for part in entry.notes.split('|'):
            if ':' in part:
                key, val = part.split(':', 1)
                extra[key.strip()] = val.strip()
    return extra


def _get_extended_status(entry):
    extra = _parse_notes_field(entry)
    custom = extra.get('status', '')
    if custom in ('skipped', 'noshow', 'hold', 'referred'):
        return custom
    return entry.status


def _build_notes(extra):
    parts = []
    for k, v in extra.items():
        if v:
            parts.append(f"{k}:{v}")
    return '|'.join(parts)


STATUS_KEYS = {
    'done': 'Done',
    'serving': 'In Progress',
    'waiting': 'Waiting',
    'skipped': 'Skipped',
    'noshow': 'No Show',
    'hold': 'On Hold',
    'referred': 'Referred',
    'cancelled': 'Cancelled',
}


@role_required('doctor', 'hospital_admin', 'super_admin')
def doctor_dashboard(request):
    return render(request, 'doctor.html')


def _get_doctor_for_user(user):
    if user.role == 'doctor':
        doctor = getattr(user, 'doctor_profile', None)
        if doctor and doctor.is_active:
            return doctor
    return None


def _today_queue_qs(doctor):
    today = timezone.now().date()
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    today_end = today_start + timedelta(days=1)
    return QueueEntry.objects.filter(
        doctor=doctor,
    ).filter(
        Q(created_at__gte=today_start, created_at__lt=today_end, scheduled_date__isnull=True) |
        Q(scheduled_date=today)
    )


class DoctorQueueView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        qs = _today_queue_qs(doctor).order_by('time')
        data = []
        for entry in qs:
            s = QueueEntrySerializer(entry).data
            s['status'] = _get_extended_status(entry)
            s['display_label'] = STATUS_KEYS.get(s['status'], s['status'])
            extra = _parse_notes_field(entry)
            s['referred_to'] = extra.get('referred_to', '')
            s['refer_reason'] = extra.get('refer_reason', '')
            s['note'] = ' | '.join(filter(None, [extra.get('diag', ''), extra.get('prx', '')]))
            data.append(s)
        return Response(data)


class DoctorQueueStatsView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        qs = _today_queue_qs(doctor)
        total = qs.count()
        all_entries = list(qs.all())
        waiting = sum(1 for e in all_entries if _get_extended_status(e) == 'waiting')
        serving = sum(1 for e in all_entries if _get_extended_status(e) == 'serving')
        done = sum(1 for e in all_entries if _get_extended_status(e) == 'done')
        skipped = sum(1 for e in all_entries if _get_extended_status(e) == 'skipped')
        noshow_count = sum(1 for e in all_entries if _get_extended_status(e) == 'noshow')
        cancelled = sum(1 for e in all_entries if _get_extended_status(e) == 'cancelled')
        est_min = waiting * 10 if waiting > 0 else 0
        return Response({
            'total': total,
            'waiting': waiting,
            'serving': serving,
            'done': done,
            'skipped': skipped,
            'noshow': noshow_count,
            'cancelled': cancelled,
            'est_time': f'~{est_min}m' if est_min else '—',
        })


class CallNextPatientView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)

        qs = _today_queue_qs(doctor)

        current = qs.filter(status='serving').first()
        if current:
            current.status = 'done'
            current.save()

        next_entry = qs.filter(status='waiting').order_by('time').first()
        if not next_entry:
            return Response({'message': 'Queue complete', 'queue_complete': True})

        next_entry.status = 'serving'
        next_entry.save()

        DoctorNotification.objects.create(
            doctor=doctor,
            type='queue',
            icon='ti-player-skip-forward',
            icon_class='ni-green',
            message=f"Called: {next_entry.patient_name} ({next_entry.token})"
        )

        s = QueueEntrySerializer(next_entry).data
        s['status'] = 'serving'
        s['display_label'] = 'In Progress'
        return Response(s)


class UpdateQueueEntryStatusView(APIView):
    permission_classes = [IsDoctor]

    def patch(self, request, pk):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        entry = get_object_or_404(QueueEntry, pk=pk, doctor=doctor)
        new_status = request.data.get('status', '')

        if new_status in ('done', 'cancelled'):
            entry.status = new_status
            entry.save()
        elif new_status in ('skipped', 'noshow', 'hold'):
            extra = _parse_notes_field(entry)
            extra['status'] = new_status
            entry.notes = _build_notes(extra)
            entry.save()
        elif new_status == 'serving':
            qs = _today_queue_qs(doctor)
            current = qs.filter(status='serving').first()
            if current and current.pk != entry.pk:
                current.status = 'done'
                current.save()
            entry.status = 'serving'
            entry.save()
        else:
            entry.status = new_status
            entry.save()

        DoctorNotification.objects.create(
            doctor=doctor,
            type='status',
            icon='ti-check',
            icon_class='ni-green',
            message=f"{entry.token} — {entry.patient_name} marked as {STATUS_KEYS.get(new_status, new_status)}"
        )

        s = QueueEntrySerializer(entry).data
        s['status'] = _get_extended_status(entry)
        s['display_label'] = STATUS_KEYS.get(s['status'], s['status'])
        return Response(s)


class AddEmergencyTokenView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        patient_name = request.data.get('patient_name', '').strip()
        if not patient_name:
            return Response({'error': 'Patient name required'}, status=400)

        token = TokenCounter.get_next_token(doctor.prefix)

        entry = QueueEntry.objects.create(
            token=token,
            patient_name=patient_name,
            patient_phone='—',
            doctor=doctor,
            doctor_name=doctor.name,
            department_name=doctor.department.name if doctor.department else '',
            visit_type='Emergency',
            time=timezone.now().time(),
            status='waiting',
            notes='complaint:Emergency case|status:emergency',
            created_by=request.user,
        )

        DoctorNotification.objects.create(
            doctor=doctor,
            type='emergency',
            icon='ti-ambulance',
            icon_class='ni-red',
            message=f"Emergency token {token} added for {patient_name}"
        )

        s = QueueEntrySerializer(entry).data
        s['status'] = 'waiting'
        s['display_label'] = 'Waiting'
        return Response(s, status=201)


class ReorderQueueView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        qs = _today_queue_qs(doctor).filter(status='waiting').order_by('time')
        count = qs.count()
        entries = list(qs)
        priority_order = {'emergency': 0, 'priority': 1, 'normal': 2, 'Walk-In': 3}
        entries.sort(key=lambda e: (priority_order.get(e.visit_type, 3), e.time or e.created_at.time()))
        base = timezone.now().time().replace(microsecond=0)
        from datetime import timedelta, datetime
        today = timezone.now().date()
        for idx, entry in enumerate(entries):
            entry.time = (datetime.combine(today, base) + timedelta(minutes=idx)).time()
        QueueEntry.objects.bulk_update(entries, ['time'])
        return Response({'message': f'Re-ordered {count} waiting tokens', 'count': count})


class RegisterPatientView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        serializer = RegisterPatientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        token = TokenCounter.get_next_token(doctor.prefix)

        complaint = data.get('complaint', 'General consultation')
        entry = QueueEntry.objects.create(
            token=token,
            patient_name=data['patient_name'],
            patient_phone=data.get('patient_phone', '—'),
            doctor=doctor,
            doctor_name=doctor.name,
            department_name=doctor.department.name if doctor.department else '',
            visit_type='Walk-In' if data['token_type'] != 'emergency' else 'Emergency',
            time=timezone.now().time(),
            status='waiting',
            notes=f"complaint:{complaint}|gender:{data.get('gender', '')}|age:{data.get('age', '')}|address:{data.get('address', '')}",
            created_by=request.user,
        )

        return Response(QueueEntrySerializer(entry).data, status=201)


class PatientDirectoryView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        q = request.query_params.get('q', '').strip().lower()
        qs = _today_queue_qs(doctor)
        if q:
            qs = qs.filter(
                Q(patient_name__icontains=q) |
                Q(token__icontains=q) |
                Q(patient_phone__icontains=q) |
                Q(notes__icontains=q)
            )
        data = []
        for entry in qs.order_by('-created_at'):
            s = QueueEntrySerializer(entry).data
            s['status'] = _get_extended_status(entry)
            s['display_label'] = STATUS_KEYS.get(s['status'], s['status'])
            data.append(s)
        return Response(data)


class VitalsView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request, queue_pk):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        entry = get_object_or_404(QueueEntry, pk=queue_pk, doctor=doctor)
        vr = entry.vital_records.first()
        if vr:
            return Response(VitalRecordSerializer(vr).data)
        return Response({
            'queue_entry': queue_pk,
            'bp': '', 'pulse': None, 'temp': None, 'spo2': None,
            'weight': None, 'height': None, 'rbs': None,
        })

    def post(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        queue_entry_id = request.data.get('queue_entry')
        entry = get_object_or_404(QueueEntry, pk=queue_entry_id, doctor=doctor)
        vr, created = VitalRecord.objects.update_or_create(
            queue_entry=entry,
            defaults={
                'bp': request.data.get('bp', ''),
                'pulse': request.data.get('pulse'),
                'temp': request.data.get('temp'),
                'spo2': request.data.get('spo2'),
                'weight': request.data.get('weight'),
                'height': request.data.get('height'),
                'rbs': request.data.get('rbs'),
            }
        )
        return Response(VitalRecordSerializer(vr).data)


class ConsultationNoteView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request, queue_pk):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        entry = get_object_or_404(QueueEntry, pk=queue_pk, doctor=doctor)
        try:
            cn = entry.consultation_note
            return Response(ConsultationNoteSerializer(cn).data)
        except ConsultationNote.DoesNotExist:
            return Response({
                'queue_entry': queue_pk,
                'diagnosis': '', 'prescription': '',
                'is_visible_to_patient': True,
            })

    def post(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        queue_entry_id = request.data.get('queue_entry')
        entry = get_object_or_404(QueueEntry, pk=queue_entry_id, doctor=doctor)
        diag = request.data.get('diagnosis', '')
        prx = request.data.get('prescription', '')
        is_visible = request.data.get('is_visible_to_patient', True)

        cn, created = ConsultationNote.objects.update_or_create(
            queue_entry=entry,
            defaults={
                'diagnosis': diag,
                'prescription': prx,
                'is_visible_to_patient': is_visible,
            }
        )

        extra = _parse_notes_field(entry)
        if diag:
            extra['diag'] = diag
        if prx:
            extra['prx'] = prx
        entry.notes = _build_notes(extra)
        entry.save()

        return Response(ConsultationNoteSerializer(cn).data)


class ReferDoctorListView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_for_user(request.user)
        doctors = Doctor.objects.filter(is_active=True, status='active')
        if doctor:
            doctors = doctors.exclude(id=doctor.id)
        data = [
            {
                'id': d.id,
                'name': d.name,
                'specialty': d.specialty or '',
                'department_name': d.department.name if d.department else '',
            }
            for d in doctors
        ]
        return Response(data)


class ReferPatientView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, queue_pk):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        entry = get_object_or_404(QueueEntry, pk=queue_pk, doctor=doctor)
        doctor_name = request.data.get('doctor', '').strip()
        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'error': 'Reason required'}, status=400)

        extra = _parse_notes_field(entry)
        extra['status'] = 'referred'
        extra['referred_to'] = doctor_name
        extra['refer_reason'] = reason
        entry.notes = _build_notes(extra)
        entry.save()

        DoctorNotification.objects.create(
            doctor=doctor,
            type='referral',
            icon='ti-arrow-forward-up',
            icon_class='ni-blue',
            message=f"{entry.patient_name} ({entry.token}) referred to {doctor_name} — {reason}"
        )

        s = QueueEntrySerializer(entry).data
        s['status'] = 'referred'
        s['display_label'] = 'Referred'
        s['referred_to'] = doctor_name
        s['refer_reason'] = reason
        return Response(s)


class DoctorScheduleView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        settings, _ = DoctorScheduleSettings.objects.get_or_create(doctor=doctor)
        return Response(DoctorScheduleSettingsSerializer(settings).data)

    def put(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        settings, _ = DoctorScheduleSettings.objects.get_or_create(doctor=doctor)
        ser = DoctorScheduleSettingsSerializer(settings, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class DoctorNotificationListView(generics.ListAPIView):
    serializer_class = DoctorNotificationSerializer
    permission_classes = [IsDoctor]

    def get_queryset(self):
        doctor = _get_doctor_for_user(self.request.user)
        if not doctor:
            return DoctorNotification.objects.none()
        return DoctorNotification.objects.filter(doctor=doctor)[:20]


class ClearNotificationsView(APIView):
    permission_classes = [IsDoctor]

    def delete(self, request):
        doctor = _get_doctor_for_user(request.user)
        if doctor:
            DoctorNotification.objects.filter(doctor=doctor).delete()
        return Response({'message': 'Notifications cleared'})


class DoctorProfileView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        return Response(DoctorProfileSerializer(doctor).data)

    # Profile updates restricted to admin only; doctors view-only


class DoctorStatusView(APIView):
    permission_classes = [IsDoctor]

    def patch(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        new_status = request.data.get('status', 'active')
        valid_statuses = ['active', 'on-leave']
        if new_status not in valid_statuses:
            return Response({'error': f'Invalid status. Choose from: {valid_statuses}'}, status=400)
        doctor.status = new_status
        doctor.save(update_fields=['status'])
        status_labels = {'active': 'Available', 'on-leave': 'On Break'}
        DoctorNotification.objects.create(
            doctor=doctor,
            type='status',
            icon='ti-toggle-left',
            icon_class='ni-blue',
            message=f"Status changed to {status_labels.get(new_status, new_status)}"
        )
        return Response({'status': new_status, 'label': status_labels.get(new_status, new_status)})


class DoctorHistoryView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_for_user(request.user)
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        base_qs = QueueEntry.objects.filter(doctor=doctor, status='done').order_by('-created_at')
        total = base_qs.count()
        qs = base_qs[(page - 1) * page_size:page * page_size]
        data = []
        for entry in qs:
            extra = _parse_notes_field(entry)
            try:
                cn = entry.consultation_note
                diag = cn.diagnosis
                rx = cn.prescription
            except ConsultationNote.DoesNotExist:
                diag = extra.get('diag', '')
                rx = extra.get('prx', '')
            data.append({
                'date': entry.created_at.strftime('%d %b') if entry.created_at else '',
                'token': entry.token,
                'name': entry.patient_name,
                'complaint': extra.get('complaint', 'General consultation'),
                'diag': diag,
                'rx': rx,
            })
        return Response({'results': data, 'total': total, 'page': page, 'page_size': page_size})
