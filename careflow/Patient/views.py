from django.db import models as db_models
from rest_framework import generics, permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User

from hospital_admin.models import Doctor, Department
from reception.models import QueueEntry
from .models import PatientProfile, FamilyMember, Appointment, DoctorReview, NotificationLog
from .serializers import (
    PatientProfileSerializer, PatientProfileUpdateSerializer,
    FamilyMemberSerializer, AppointmentSerializer, AppointmentCreateSerializer,
    DoctorReviewSerializer, DoctorReviewCreateSerializer,
    NotificationLogSerializer, GuestBookingSerializer,
)


@login_required
def patient_dashboard(request):
    return render(request, 'patient.html')


class PatientRegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        phone = request.data.get('phone', '').strip()
        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        email = request.data.get('email', '').strip()
        date_of_birth = request.data.get('date_of_birth')
        blood_group = request.data.get('blood_group', '')
        address = request.data.get('address', '')

        if not phone or not first_name:
            return Response({'error': 'Phone and name are required'}, status=400)
        if User.objects.filter(phone=phone).exists():
            return Response({'error': 'Phone already registered'}, status=400)

        username = f"pat_{phone[-10:]}"
        base_username = username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{suffix}"
            suffix += 1

        user = User(
            username=username,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=User.Role.PATIENT,
        )
        user.set_unusable_password()
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
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'email': user.email,
                'role': user.role,
            },
            'profile': PatientProfileSerializer(profile).data,
        }, status=status.HTTP_201_CREATED)


class PatientProfileView(APIView):
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

        user_fields = ['first_name', 'last_name', 'email']
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

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        return FamilyMember.objects.filter(patient=profile, is_active=True)

    def perform_create(self, serializer):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        serializer.save(patient=profile)


class FamilyMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FamilyMemberSerializer

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
        dept_filter = request.query_params.get('department')
        doctors = Doctor.objects.filter(is_active=True, status='active')
        if dept_filter:
            doctors = doctors.filter(department__name__iexact=dept_filter)

        data = []
        for d in doctors:
            waiting = QueueEntry.objects.filter(doctor=d, status='waiting').count()
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
                'morning_slots': d.morning_slots,
                'evening_slots': d.evening_slots,
                'waiting_count': waiting,
                'slots_left': max(0, d.slots_per_day - waiting),
                'status': d.status,
            })
        return Response(data)


class DoctorPublicDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        d = Doctor.objects.filter(pk=pk, is_active=True).first()
        if not d:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)
        waiting = QueueEntry.objects.filter(doctor=d, status='waiting').count()
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
            'morning_slots': d.morning_slots,
            'evening_slots': d.evening_slots,
            'waiting_count': waiting,
            'slots_left': max(0, d.slots_per_day - waiting),
            'status': d.status,
        }
        return Response(data)


class AvailableSlotsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date_str = request.query_params.get('date')

        if not doctor_id or not date_str:
            return Response({'error': 'doctor_id and date are required'}, status=400)

        from datetime import datetime, date
        try:
            selected_date = date.fromisoformat(date_str)
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        day_of_week = selected_date.weekday()
        doctor = Doctor.objects.filter(id=doctor_id, is_active=True).first()
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)

        slots = list(doctor.time_slots.filter(day_of_week=day_of_week))
        existing_appointments = Appointment.objects.filter(
            doctor_name=doctor.name,
            appointment_date=selected_date,
            status__in=['confirmed', 'scheduled'],
        )

        booked_times = set()
        for apt in existing_appointments:
            booked_times.add(apt.appointment_time.strftime('%H:%M'))

        available = []
        for slot in slots:
            time_key = slot.start_time.strftime('%H:%M')
            if time_key not in booked_times:
                available.append({
                    'time': time_key,
                    'label': slot.start_time.strftime('%I:%M %p').lstrip('0'),
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
        doctor = Doctor.objects.filter(name=serializer.validated_data['doctor_name']).first()
        prefix = doctor.prefix if doctor else 'X'
        token = TokenCounter.get_next_token(prefix)
        serializer.save(patient=profile, token=token)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Return the created appointment using AppointmentSerializer for proper representation
        response_serializer = AppointmentSerializer(serializer.instance)
        from rest_framework import status as drf_status
        return Response(response_serializer.data, status=drf_status.HTTP_201_CREATED)


class AppointmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        return Appointment.objects.filter(patient=profile)

    def perform_destroy(self, instance):
        from datetime import datetime, timedelta
        slot_datetime = datetime.combine(instance.appointment_date, instance.appointment_time)
        if slot_datetime - datetime.now() < timedelta(hours=1):
            raise serializers.ValidationError('Cancellation not allowed within 1 hour of appointment')
        instance.status = Appointment.Status.CANCELLED
        instance.save()



class QueueStatusView(APIView):
    def get(self, request):
        doctor_name = request.query_params.get('doctor')
        token = request.query_params.get('token')
        if not doctor_name or not token:
            return Response({'error': 'doctor and token params required'}, status=400)
        entries = QueueEntry.objects.filter(
            doctor_name__icontains=doctor_name
        ).exclude(status__in=['done', 'cancelled']).order_by('time')
        now_serving = entries.filter(status='serving').first()
        ahead = 0
        my_entry = entries.filter(token=token).first()
        if my_entry and now_serving:
            all_ids = list(entries.values_list('id', flat=True))
            my_pos = all_ids.index(my_entry.id)
            serving_pos = all_ids.index(now_serving.id) if now_serving.id in all_ids else 0
            ahead = max(0, my_pos - serving_pos)
        return Response({
            'now_serving': now_serving.token if now_serving else None,
            'tokens_ahead': ahead,
            'total_waiting': entries.filter(status='waiting').count(),
            'my_status': my_entry.status if my_entry else None,
        })


class MyBookingsView(generics.ListAPIView):
    serializer_class = AppointmentSerializer

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

    def get_queryset(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        return NotificationLog.objects.filter(patient=profile)


class NotificationMarkReadView(APIView):
    def patch(self, request, pk):
        profile, _ = PatientProfile.objects.get_or_create(user=request.user)
        notification = NotificationLog.objects.filter(pk=pk, patient=profile).first()
        if not notification:
            return Response({'error': 'Notification not found'}, status=404)
        notification.is_read = True
        notification.save()
        return Response({'status': 'ok'})


class GuestBookingView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = GuestBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        doctor = Doctor.objects.filter(pk=data['doctor_id'], is_active=True).first()
        if not doctor:
            return Response({'error': 'Doctor not found'}, status=404)
        from datetime import date
        if data['appointment_date'] < date.today():
            return Response({'error': 'Cannot book for past date'}, status=400)
        guest_name = data.get('patient_name', '') or f'Guest_{data["phone"][-6:]}'
        username = f"guest_{data['phone'][-10:]}"
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                'phone': data['phone'],
                'first_name': guest_name,
                'role': User.Role.PATIENT,
            }
        )
        profile, _ = PatientProfile.objects.get_or_create(user=user)
        from reception.models import TokenCounter
        token = TokenCounter.get_next_token(doctor.prefix)
        appointment = Appointment.objects.create(
            patient=profile,
            doctor_name=doctor.name,
            doctor_specialty=doctor.specialty,
            department_name=doctor.department.name if doctor.department else '',
            location=doctor.department.name if doctor.department else '',
            appointment_date=data['appointment_date'],
            appointment_time=data['appointment_time'],
            token=token,
            status=Appointment.Status.PENDING,
            notes=data.get('notes', ''),
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
