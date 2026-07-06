import logging
from django.db import models as db_models
from django.db import transaction
from rest_framework import generics, permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.contrib.auth import login as auth_login
from accounts.decorators import role_required
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Q

from hospital_admin.models import Doctor, Department
from reception.models import QueueEntry
from .models import PatientProfile, FamilyMember, Appointment, DoctorReview, NotificationLog
from .serializers import (
    PatientProfileSerializer, PatientProfileUpdateSerializer,
    FamilyMemberSerializer, AppointmentSerializer, AppointmentCreateSerializer,
    DoctorReviewSerializer, DoctorReviewCreateSerializer,
    NotificationLogSerializer, GuestBookingSerializer,
)

logger = logging.getLogger(__name__)


@role_required('patient')
def patient_dashboard(request):
    return render(request, 'patient.html')


class IsPatient(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.Role.PATIENT


BOOKED_APPOINTMENT_STATUSES = [
    Appointment.Status.PENDING,
    Appointment.Status.CONFIRMED,
    Appointment.Status.SCHEDULED,
    Appointment.Status.RESCHEDULED,
]


def _slot_is_available(doctor, appointment_date, appointment_time, exclude_appointment_id=None):
    if not doctor or not appointment_date or not appointment_time:
        return False

    appointment_qs = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        status__in=BOOKED_APPOINTMENT_STATUSES,
    )
    if exclude_appointment_id:
        appointment_qs = appointment_qs.exclude(pk=exclude_appointment_id)

    queue_qs = QueueEntry.objects.filter(
        doctor=doctor,
        scheduled_date=appointment_date,
        time=appointment_time,
        status__in=['waiting', 'arrived', 'serving'],
    )

    return not appointment_qs.exists() and not queue_qs.exists()


class PatientRegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        phone = request.data.get('phone', '').strip()
        name = request.data.get('name', '').strip()
        email = request.data.get('email', '').strip()
        date_of_birth = request.data.get('date_of_birth')
        blood_group = request.data.get('blood_group', '')
        address = request.data.get('address', '')

        if not phone or not name:
            return Response({'error': 'Phone and name are required'}, status=400)
        if User.objects.filter(phone=phone).exists():
            return Response({'error': 'Phone already registered'}, status=400)

        user = User(
            phone=phone,
            name=name,
            email=email,
            role=User.Role.PATIENT,
        )
        user.save()

        profile = PatientProfile.objects.create(
            user=user,
            date_of_birth=date_of_birth,
            blood_group=blood_group,
            address=address,
        )

        refresh = RefreshToken.for_user(user)
        auth_login(request, user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'name': user.name,
                'phone': user.phone,
                'email': user.email,
                'role': user.role,
            },
            'profile': PatientProfileSerializer(profile).data,
        }, status=status.HTTP_201_CREATED)


class PatientProfileView(APIView):
    permission_classes = [IsPatient]

    def get(self, request):
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        return Response(PatientProfileSerializer(profile).data)

    def patch(self, request):
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        user = request.user

        profile_fields = ['date_of_birth', 'blood_group', 'address']
        profile_data = {k: v for k, v in request.data.items() if k in profile_fields}
        if profile_data:
            p_serializer = PatientProfileUpdateSerializer(profile, data=profile_data, partial=True)
            p_serializer.is_valid(raise_exception=True)
            p_serializer.save()

        user_fields = ['name', 'email', 'phone']
        changed = False
        for field in user_fields:
            if field in request.data:
                setattr(user, field, request.data[field])
                changed = True
        if changed:
            user.save()

        return Response(PatientProfileSerializer(profile).data)


class FamilyMemberListCreateView(generics.ListCreateAPIView):
    serializer_class = FamilyMemberSerializer
    permission_classes = [IsPatient]

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        return FamilyMember.objects.filter(patient=profile, is_active=True)

    def perform_create(self, serializer):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        serializer.save(patient=profile)


class FamilyMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FamilyMemberSerializer
    permission_classes = [IsPatient]

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        return FamilyMember.objects.filter(patient=profile)


class DepartmentListView(generics.ListAPIView):
    queryset = Department.objects.filter(is_active=True)
    serializer_class = None
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        depts = Department.objects.filter(is_active=True)
        data = [{'id': d.id, 'name': d.name, 'icon': d.icon} for d in depts]
        return Response(data)


class DoctorPublicListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        today_end = today_start + timedelta(days=1)
        dept_filter = request.query_params.get('department')
        doctors = Doctor.objects.filter(is_active=True, status='active')
        if dept_filter:
            doctors = doctors.filter(department__name__iexact=dept_filter)

        data = []
        for d in doctors:
            waiting = QueueEntry.objects.filter(
                doctor=d,
            ).filter(
                Q(created_at__gte=today_start, created_at__lt=today_end, scheduled_date__isnull=True) |
                Q(status='waiting', scheduled_date__isnull=True) |
                Q(scheduled_date=today, status='waiting')
            ).count()
            avg_rating = DoctorReview.objects.filter(doctor=d).aggregate(db_models.Avg('rating'))['rating__avg']
            data.append({
                'id': d.id,
                'name': d.name,
                'specialty': d.specialty,
                'department': d.department.name if d.department else '',
                'qualification': d.qualification,
                'prefix': d.prefix,
                'avatar_color': d.avatar_color,
                'rating': round(avg_rating, 1) if avg_rating else None,
                'slots_per_day': d.slots_per_day,
                'days_available': d.days_available,
                'day_slots': d.day_slots,
                'night_slots': d.night_slots,
                'waiting_count': waiting,
                'slots_left': max(0, d.slots_per_day - waiting),
                'status': d.status,
                'consultation_fee': float(d.consultation_fee) if d.consultation_fee else 0,
            })
        return Response(data)


class DoctorPublicDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        d = Doctor.objects.filter(pk=pk, is_active=True).first()
        if not d:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        today_end = today_start + timedelta(days=1)
        waiting = QueueEntry.objects.filter(
            doctor=d,
        ).filter(
            Q(created_at__gte=today_start, created_at__lt=today_end, scheduled_date__isnull=True) |
            Q(status='waiting', scheduled_date__isnull=True) |
            Q(scheduled_date=today, status='waiting')
        ).count()
        avg_rating = DoctorReview.objects.filter(doctor=d).aggregate(db_models.Avg('rating'))['rating__avg']
        reviews = DoctorReview.objects.filter(doctor=d).order_by('-created_at')[:10]
        data = {
            'id': d.id,
            'name': d.name,
            'specialty': d.specialty,
            'department': d.department.name if d.department else '',
            'qualification': d.qualification,
            'prefix': d.prefix,
            'avatar_color': d.avatar_color,
            'rating': round(avg_rating, 1) if avg_rating else None,
            'reviews': DoctorReviewSerializer(reviews, many=True).data,
            'slots_per_day': d.slots_per_day,
            'days_available': d.days_available,
            'day_slots': d.day_slots,
            'night_slots': d.night_slots,
            'waiting_count': waiting,
            'slots_left': max(0, d.slots_per_day - waiting),
            'status': d.status,
            'consultation_fee': float(d.consultation_fee) if d.consultation_fee else 0,
        }
        return Response(data)


class AvailableSlotsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date_str = request.query_params.get('date')

        if not doctor_id or not date_str:
            return Response({'error': 'doctor_id and date are required'}, status=400)

        try:
            selected_date = date.fromisoformat(date_str)
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        if selected_date < date.today():
            return Response({'error': 'Cannot fetch slots for a past date'}, status=400)

        day_of_week = selected_date.weekday()
        doctor = Doctor.objects.filter(id=doctor_id, is_active=True).first()
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)

        time_slots_qs = doctor.time_slots.filter(day_of_week=day_of_week)
        if time_slots_qs.exists():
            slot_times = [s.start_time.strftime('%H:%M') for s in time_slots_qs]
        else:
            slot_times = []
            for range_str in [doctor.day_slots, doctor.night_slots]:
                if not range_str:
                    continue
                for sep in ['–', '-']:
                    if sep in range_str:
                        parts = range_str.split(sep)
                        if len(parts) == 2:
                            try:
                                start_hour = datetime.strptime(parts[0].strip(), '%H:%M').hour
                                end_hour = datetime.strptime(parts[1].strip(), '%H:%M').hour
                            except ValueError:
                                continue
                            for hour in range(start_hour, end_hour):
                                slot_times.append(f'{hour:02d}:00')
                        break
            if not slot_times:
                slot_times = [f'{h:02d}:00' for h in range(9, 17)]

        existing_appointments = Appointment.objects.filter(
            doctor_name=doctor.name,
            appointment_date=selected_date,
            status__in=['confirmed', 'scheduled', 'pending'],
        )

        existing_queue = QueueEntry.objects.filter(
            doctor=doctor,
            scheduled_date=selected_date,
            status__in=['waiting'],
        )

        booked_times = set()
        for apt in existing_appointments:
            booked_times.add(apt.appointment_time.strftime('%H:%M'))
        for entry in existing_queue:
            booked_times.add(entry.time.strftime('%H:%M'))

        available = []
        for time_key in slot_times:
            if time_key not in booked_times:
                from datetime import datetime as dt
                hour = int(time_key.split(':')[0])
                period = 'PM' if hour >= 12 else 'AM'
                disp_hour = hour % 12 or 12
                available.append({
                    'time': time_key,
                    'label': f'{disp_hour}:{time_key.split(":")[1]} {period}',
                })

        return Response({
            'date': date_str,
            'day': selected_date.strftime('%A'),
            'doctor_id': doctor.id,
            'doctor_name': doctor.name,
            'slots': available,
            'total_available': len(available),
        })


class AppointmentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsPatient]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AppointmentCreateSerializer
        return AppointmentSerializer

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        qs = Appointment.objects.filter(patient=profile)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        from reception.models import TokenCounter
        from hospital_admin.models import Doctor
        doctor_id = serializer.validated_data.get('doctor_id')
        doctor = None
        if doctor_id:
            doctor = Doctor.objects.filter(id=doctor_id, is_active=True).first()
        if not doctor:
            doctor = Doctor.objects.filter(name=serializer.validated_data.get('doctor_name', ''), is_active=True).first()
        if not doctor:
            raise serializers.ValidationError({'doctor_id': 'Valid doctor is required'})
        doctor = Doctor.objects.select_for_update().get(pk=doctor.pk)
        appointment_date = serializer.validated_data.get('appointment_date', timezone.now().date())
        appointment_time = serializer.validated_data.get('appointment_time', timezone.now().time())
        if appointment_date < date.today():
            raise serializers.ValidationError({'appointment_date': 'Cannot book for a past date'})
        if not _slot_is_available(doctor, appointment_date, appointment_time):
            raise serializers.ValidationError({'appointment_time': 'This slot is already booked'})
        doctor_name = doctor.name if doctor else serializer.validated_data.get('doctor_name', '')
        prefix = doctor.prefix if doctor else 'X'
        token = TokenCounter.get_next_token(prefix)
        serializer.save(patient=profile, token=token, doctor=doctor, doctor_name=doctor_name)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.perform_create(serializer)
            appointment = serializer.instance
            doctor = appointment.doctor
            if not doctor and appointment.doctor_name:
                doctor = Doctor.objects.filter(name=appointment.doctor_name, is_active=True).first()
            if doctor:
                QueueEntry.objects.create(
                    token=appointment.token,
                    patient_name=appointment.patient.user.name,
                    patient_phone=appointment.patient.user.phone or '',
                    doctor=doctor,
                    doctor_name=doctor.name,
                    department_name=doctor.department.name if doctor.department else '',
                    visit_type='Booking',
                    time=appointment.appointment_time,
                    status='waiting',
                    scheduled_date=appointment.appointment_date,
                    notes=f"Appointment id: {appointment.id}",
                )

        try:
            NotificationLog.objects.create(
                patient=appointment.patient,
                type=NotificationLog.Type.BOOKING_CONFIRMED,
                title='Appointment Booked',
                message=f'Your appointment with {appointment.doctor_name} on {appointment.appointment_date} at {appointment.appointment_time} Token: {appointment.token}',
            )
        except Exception as e:
            logger.exception('Failed to create NotificationLog for appointment %s: %s', appointment.id, e)

        response_serializer = AppointmentSerializer(appointment)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AppointmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsPatient]
    http_method_names = ['get', 'delete', 'head', 'options']

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        return Appointment.objects.filter(patient=profile)

    def destroy(self, request, *args, **kwargs):
        from reception.models import QueueEntry
        instance = self.get_object()
        slot_datetime = timezone.make_aware(datetime.combine(instance.appointment_date, instance.appointment_time))
        if slot_datetime - timezone.now() < timedelta(hours=1):
            raise serializers.ValidationError('Cancellation not allowed within 1 hour of appointment')
        instance.status = Appointment.Status.CANCELLED
        instance.save()
        QueueEntry.objects.filter(token=instance.token, doctor_name=instance.doctor_name).update(
            status='cancelled', cancel_source='patient-app',
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AppointmentRescheduleView(APIView):
    permission_classes = [IsPatient]

    def patch(self, request, pk):
        from reception.models import QueueEntry, TokenCounter
        from hospital_admin.models import Doctor
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        appointment = Appointment.objects.filter(pk=pk, patient=profile).first()
        if not appointment:
            return Response({'error': 'Appointment not found'}, status=status.HTTP_404_NOT_FOUND)

        new_date = request.data.get('appointment_date')
        new_time_raw = request.data.get('appointment_time')
        if not new_date or not new_time_raw:
            return Response({'error': 'appointment_date and appointment_time are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_time = datetime.strptime(new_time_raw, '%H:%M').time() if isinstance(new_time_raw, str) else new_time_raw
        except (ValueError, TypeError):
            return Response({'error': 'Invalid time format. Use HH:MM'}, status=status.HTTP_400_BAD_REQUEST)

        slot_datetime = timezone.make_aware(datetime.combine(appointment.appointment_date, appointment.appointment_time))
        if slot_datetime - timezone.now() < timedelta(hours=1):
            return Response({'error': 'Rescheduling not allowed within 1 hour of appointment'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            parsed_date = date.fromisoformat(new_date) if isinstance(new_date, str) else new_date
        except (ValueError, TypeError):
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        if parsed_date < date.today():
            return Response({'error': 'Cannot reschedule to a past date'}, status=status.HTTP_400_BAD_REQUEST)

        doctor = appointment.doctor
        if not doctor and appointment.doctor_name:
            doctor = Doctor.objects.filter(name=appointment.doctor_name, is_active=True).first()
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            doctor = Doctor.objects.select_for_update().get(pk=doctor.pk)
            if not _slot_is_available(doctor, parsed_date, new_time, exclude_appointment_id=appointment.id):
                return Response({'error': 'This slot is already booked'}, status=status.HTTP_400_BAD_REQUEST)
            prefix = doctor.prefix
            new_token = TokenCounter.get_next_token(prefix)

            QueueEntry.objects.filter(token=appointment.token, doctor_name=appointment.doctor_name).update(
                status='cancelled',
                notes=f"Cancelled on reschedule to {parsed_date}. Previous token: {appointment.token}",
            )

            appointment.appointment_date = parsed_date
            appointment.appointment_time = new_time
            appointment.token = new_token
            appointment.status = Appointment.Status.RESCHEDULED
            appointment.save()

            QueueEntry.objects.create(
                token=new_token,
                patient_name=appointment.patient.user.name,
                patient_phone=appointment.patient.user.phone or '',
                doctor=doctor,
                doctor_name=doctor.name,
                department_name=doctor.department.name if doctor.department else '',
                visit_type='Booking',
                time=new_time,
                status='waiting',
                scheduled_date=parsed_date,
                notes=f"Appointment id: {appointment.id}",
            )

        NotificationLog.objects.create(
            patient=profile,
            type=NotificationLog.Type.BOOKING_CONFIRMED,
            title='Appointment Rescheduled',
            message=f'Your appointment has been rescheduled to {parsed_date} at {new_time}',
        )

        return Response(AppointmentSerializer(appointment).data)


class QueueStatusView(APIView):
    def get(self, request):
        doctor_name = request.query_params.get('doctor')
        doctor_id = request.query_params.get('doctor_id')
        token = request.query_params.get('token')
        if not token:
            return Response({'error': 'token param required'}, status=400)
        if not doctor_name and not doctor_id:
            return Response({'error': 'doctor or doctor_id param required'}, status=400)

        if doctor_id:
            base_qs = QueueEntry.objects.filter(doctor_id=doctor_id)
        elif doctor_name:
            base_qs = QueueEntry.objects.filter(doctor_name=doctor_name)
        else:
            base_qs = QueueEntry.objects.none()

        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        today_end = today_start + timedelta(days=1)
        my_entry = base_qs.exclude(status__in=['done', 'cancelled']).filter(token=token).first()
        if my_entry and my_entry.scheduled_date:
            entries = base_qs.filter(scheduled_date=my_entry.scheduled_date)
        else:
            entries = base_qs.filter(
                Q(created_at__gte=today_start, created_at__lt=today_end, scheduled_date__isnull=True) |
                Q(scheduled_date=today)
            )
        entries = entries.exclude(status__in=['done', 'cancelled']).order_by('time')

        now_serving = entries.filter(status='serving').first()
        my_entry = entries.filter(token=token).first()
        ahead = 0
        if my_entry:
            all_ids = list(entries.values_list('id', flat=True))
            if my_entry.id in all_ids:
                my_pos = all_ids.index(my_entry.id)
                if now_serving and now_serving.id in all_ids:
                    serving_pos = all_ids.index(now_serving.id)
                    ahead = max(0, my_pos - serving_pos)
                else:
                    ahead = my_pos

        # Calculate avg consult time from completed entries today
        completed_today_qs = base_qs.filter(
            status='done',
            updated_at__gte=today_start,
            updated_at__lt=today_end,
        )
        completed_count = completed_today_qs.count()
        avg_consult = 0
        if completed_count > 0:
            total_secs = 0
            samples = 0
            for entry in completed_today_qs:
                if entry.created_at and entry.updated_at:
                    diff = (entry.updated_at - entry.created_at).total_seconds()
                    if 60 <= diff <= 3600:
                        total_secs += diff
                        samples += 1
            if samples > 0:
                avg_consult = round(total_secs / samples / 60)

        estimated_wait = avg_consult * ahead if avg_consult and ahead else 0

        return Response({
            'now_serving': now_serving.token if now_serving else None,
            'tokens_ahead': ahead,
            'total_waiting': entries.filter(status='waiting').count(),
            'my_status': my_entry.status if my_entry else None,
            'avg_consult_time': avg_consult,
            'completed_today': completed_count,
            'estimated_wait': estimated_wait,
        })


class MyBookingsView(generics.ListAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsPatient]

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        from datetime import date
        filter_type = self.request.query_params.get('filter', 'upcoming')
        qs = Appointment.objects.filter(patient=profile)
        if filter_type == 'upcoming':
            qs = qs.filter(appointment_date__gte=date.today()).exclude(status__in=['cancelled', 'completed', 'missed'])
        elif filter_type == 'history':
            qs = qs.filter(
                status__in=['completed', 'cancelled', 'missed']
            ) | qs.filter(appointment_date__lt=date.today())
        return qs.order_by('-appointment_date', '-appointment_time')[:20]


class DoctorReviewCreateView(APIView):
    permission_classes = [IsPatient]

    def post(self, request):
        serializer = DoctorReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        appointment = Appointment.objects.filter(
            pk=serializer.validated_data['appointment_id'],
            patient=profile,
            status=Appointment.Status.COMPLETED,
        ).first()
        if not appointment:
            return Response({'error': 'Completed appointment not found'}, status=404)
        if DoctorReview.objects.filter(patient=profile, appointment=appointment).exists():
            return Response({'error': 'Already reviewed this appointment'}, status=400)
        doctor = Doctor.objects.filter(name=appointment.doctor_name).first()
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        review = DoctorReview.objects.create(
            patient=profile,
            doctor=doctor,
            appointment=appointment,
            rating=serializer.validated_data['rating'],
            comment=serializer.validated_data.get('comment', ''),
        )
        return Response(DoctorReviewSerializer(review).data, status=201)


class DoctorReviewsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, doctor_id):
        doctor = Doctor.objects.filter(pk=doctor_id, is_active=True).first()
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        reviews = DoctorReview.objects.filter(doctor=doctor).order_by('-created_at')
        avg = reviews.aggregate(db_models.Avg('rating'))['rating__avg']
        return Response({
            'doctor_id': doctor.id,
            'doctor_name': doctor.name,
            'average_rating': round(avg, 1) if avg else None,
            'total_reviews': reviews.count(),
            'reviews': DoctorReviewSerializer(reviews, many=True).data,
        })


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationLogSerializer
    permission_classes = [IsPatient]

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        return NotificationLog.objects.filter(patient=profile)


class NotificationMarkReadView(APIView):
    permission_classes = [IsPatient]

    def patch(self, request, pk):
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        notification = NotificationLog.objects.filter(pk=pk, patient=profile).first()
        if not notification:
            return Response({'error': 'Notification not found'}, status=404)
        notification.is_read = True
        notification.save()
        return Response({'status': 'ok'})


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsPatient]

    def patch(self, request):
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        updated = NotificationLog.objects.filter(patient=profile, is_read=False).update(is_read=True)
        return Response({'updated': updated})


class GuestBookingView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        from reception.models import TokenCounter, QueueEntry
        serializer = GuestBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        doctor = Doctor.objects.filter(pk=data['doctor_id'], is_active=True).first()
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        from datetime import date
        if data['appointment_date'] < date.today():
            return Response({'error': 'Cannot book for past date'}, status=400)
        if not _slot_is_available(doctor, data['appointment_date'], data['appointment_time']):
            return Response({'error': 'This slot is already booked'}, status=status.HTTP_400_BAD_REQUEST)
        guest_name = data.get('patient_name', '') or f'Guest_{data["phone"][-6:]}'
        existing_user = User.objects.filter(phone=data['phone']).first()
        if existing_user and existing_user.role != User.Role.PATIENT:
            return Response(
                {'error': 'Phone number is already registered as a staff member. Please use a different contact.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user, _ = User.objects.get_or_create(
            phone=data['phone'],
            defaults={
                'name': guest_name,
                'role': User.Role.PATIENT,
            }
        )
        profile, _ = PatientProfile.objects.get_or_create(user=user)
        with transaction.atomic():
            doctor = Doctor.objects.select_for_update().get(pk=doctor.pk)
            if not _slot_is_available(doctor, data['appointment_date'], data['appointment_time']):
                return Response({'error': 'This slot is already booked'}, status=status.HTTP_400_BAD_REQUEST)
            token = TokenCounter.get_next_token(doctor.prefix)
            appointment = Appointment.objects.create(
                patient=profile,
                doctor=doctor,
                doctor_name=doctor.name,
                doctor_specialty=doctor.specialty,
                department_name=doctor.department.name if doctor.department else '',
                location=doctor.department.name if doctor.department else '',
                appointment_date=data['appointment_date'],
                appointment_time=data['appointment_time'],
                token=token,
                fee=doctor.consultation_fee if doctor.consultation_fee else None,
                status=Appointment.Status.PENDING,
                notes=data.get('notes', ''),
            )

            QueueEntry.objects.create(
                token=token,
                patient_name=user.name,
                patient_phone=user.phone or '',
                doctor=doctor,
                doctor_name=doctor.name,
                department_name=doctor.department.name if doctor.department else '',
                visit_type='Booking',
                time=data['appointment_time'],
                status='waiting',
                scheduled_date=data['appointment_date'],
                notes=f"Appointment id: {appointment.id}",
            )

        NotificationLog.objects.create(
            patient=profile,
            type=NotificationLog.Type.BOOKING_CONFIRMED,
            title='Appointment Booked',
            message=f'Your appointment with {doctor.name} on {data["appointment_date"]} at {data["appointment_time"]} Token: {token}',
        )
        return Response({
            'token': token,
            'doctor_name': doctor.name,
            'appointment_date': data['appointment_date'],
            'appointment_time': data['appointment_time'],
            'status': appointment.status,
        }, status=201)


class QueueQRView(APIView):
    def get(self, request):
        token = request.query_params.get('token')
        doctor_name = request.query_params.get('doctor')
        if not token or not doctor_name:
            return Response({'error': 'token and doctor params required'}, status=400)
        try:
            import qrcode
            from io import BytesIO
            import base64
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(f'CareFlow Token: {token}\nDoctor: {doctor_name}')
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')
            buf = BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode()
            return Response({'qr_base64': b64, 'token': token, 'doctor_name': doctor_name})
        except ImportError:
            return Response({'qr_base64': None, 'token': token, 'doctor_name': doctor_name, 'error': 'QR library not installed'})
