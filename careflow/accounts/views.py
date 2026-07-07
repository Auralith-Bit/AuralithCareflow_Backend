import random
import time
from django.shortcuts import get_object_or_404, render
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Notification
from .serializers import UserSerializer, PermissionSerializer, GroupSerializer, UserDetailSerializer, NotificationSerializer
from .permissions import IsHospitalAdmin, IsSuperAdmin
from django.contrib.auth.models import Group, Permission
from hospital_admin.models import Doctor


# In-memory OTP store for demo (phone -> {otp, time})
_otp_store = {}

def _generate_otp():
    return str(random.randint(100000, 999999))

def _store_otp(phone, otp):
    _otp_store[phone] = {'otp': otp, 'time': time.time()}

def _verify_otp(phone, otp):
    data = _otp_store.get(phone)
    if not data:
        return False
    if time.time() - data['time'] > 300:
        del _otp_store[phone]
        return False
    if data['otp'] == otp:
        del _otp_store[phone]
        return True
    return False


class CheckPhoneView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        phone = request.data.get('phone', '').strip()
        if not phone:
            return Response({'error': 'Phone number is required'}, status=400)
        user = User.objects.filter(phone=phone).first()
        return Response({
            'exists': user is not None,
            'user': UserSerializer(user).data if user else None,
        })


class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        phone = request.data.get('phone', '').strip()
        if not phone:
            return Response({'error': 'Phone number is required'}, status=400)
        otp = _generate_otp()
        _store_otp(phone, otp)
        return Response({
            'sent': True,
            'otp': otp,
        })


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        phone = request.data.get('phone', '').strip()
        otp = request.data.get('otp', '').strip()
        if not phone or not otp:
            return Response({'error': 'Phone and OTP are required'}, status=400)
        if not _verify_otp(phone, otp):
            return Response({'error': 'Invalid or expired OTP'}, status=400)
        user = User.objects.filter(phone=phone).first()
        if not user:
            return Response({'error': 'User not found. Please register first.'}, status=400)
        refresh = RefreshToken.for_user(user)
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        })



class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        phone = request.data.get('phone')
        password = request.data.get('password')
        if password:
            user = authenticate(username=phone, password=password)
            if user:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': UserSerializer(user).data,
                })
        return Response({'error': 'Use phone + OTP to login'}, status=401)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        phone = request.data.get('phone', '').strip()
        name = request.data.get('name', '').strip()
        email = request.data.get('email', '').strip()
        gender = request.data.get('gender', '').strip()
        date_of_birth = request.data.get('date_of_birth', None)
        address = request.data.get('address', '').strip()

        if not phone or not name:
            return Response({'error': 'Phone and name are required'}, status=400)
        if User.objects.filter(phone=phone).exists():
            return Response({'error': 'Phone already registered'}, status=400)

        user = User(
            phone=phone,
            name=name,
            email=email,
            role=User.Role.PATIENT,
            gender=gender,
            date_of_birth=date_of_birth if date_of_birth else None,
            address=address,
        )
        user.save()

        from Patient.models import PatientProfile
        PatientProfile.objects.get_or_create(user=user)

        refresh = RefreshToken.for_user(user)
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        auth_logout(request)
        return redirect('login')


class CreateStaffView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        name = request.data.get('name', '').strip()
        role = request.data.get('role', '').strip().lower()

        if not name or role not in ('receptionist', 'doctor', 'hospital_admin'):
            return Response({'error': 'Valid name and role are required'}, status=400)

        user_role = request.user.role
        if user_role == 'super_admin' and role != 'hospital_admin':
            return Response({'error': 'Super admin can only create hospital admin accounts'}, status=403)
        if user_role == 'hospital_admin' and role not in ('doctor', 'receptionist'):
            return Response({'error': 'Hospital admin can only create doctors and receptionists'}, status=403)
        if user_role not in ('super_admin', 'hospital_admin'):
            return Response({'error': 'You do not have permission to create staff'}, status=403)

        employee_id = User.generate_employee_id(role)
        if not employee_id:
            return Response({'error': 'Could not generate employee ID'}, status=500)

        if User.objects.filter(employee_id=employee_id).exists():
            return Response({'error': 'Employee ID collision. Try again.'}, status=500)

        password = User.generate_password()

        user = User(
            name=name,
            employee_id=employee_id,
            role=role,
            is_active=False,
        )
        user.set_password(password)
        user.save()

        Notification.send(
            user=request.user,
            type='staff_added',
            title='👤 Staff Created',
            message=f"{name} added as {role.replace('_', ' ').title()} (ID: {employee_id})",
            icon='ti-user-plus',
            icon_color='ni-green',
        )
        for admin in User.objects.filter(role='hospital_admin', is_active=True).exclude(pk=request.user.pk):
            Notification.send(
                user=admin,
                type='staff_added',
                title='👤 Staff Created',
                message=f"{name} added as {role.replace('_', ' ').title()} by {request.user.name} (ID: {employee_id})",
                icon='ti-user-plus',
                icon_color='ni-green',
            )

        if role == 'doctor':
            used = set(Doctor.objects.values_list('prefix', flat=True))
            prefix = next((l for l in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if l not in used), None)
            if not prefix:
                max_num = max(
                    (int(p[1:]) for p in used if p.startswith('D') and p[1:].isdigit()),
                    default=0
                )
                prefix = f'D{max_num + 1}'
            Doctor.objects.create(
                user=user,
                name=name,
                employee_id=employee_id,
                prefix=prefix,
            )

        return Response({
            'user': UserSerializer(user).data,
            'employee_id': employee_id,
            'password': password,
        }, status=201)


class ToggleUserStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_active = not user.is_active
        user.save()
        return Response(UserSerializer(user).data)


class UpdateUserView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        name = request.data.get('name', '').strip()
        phone = request.data.get('phone', '').strip()
        email = request.data.get('email', '').strip()

        if phone and phone != user.phone:
            if User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
                return Response({'error': 'Phone already in use'}, status=400)
        if not name:
            return Response({'error': 'Name is required'}, status=400)

        user.name = name
        user.phone = phone
        user.email = email
        user.save()
        return Response(UserSerializer(user).data)


class DeleteStaffView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.role == 'super_admin':
            return Response({'error': 'Cannot delete this user'}, status=400)
        user.delete()
        return Response({'message': 'Staff deleted'}, status=200)


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        qs = User.objects.all()
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        return qs


class PermissionListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def get(self, request):
        perms = Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        )
        return Response(PermissionSerializer(perms, many=True).data)


class GroupListCreateView(generics.ListCreateAPIView):
    queryset = Group.objects.prefetch_related('permissions').all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]


class GroupDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Group.objects.prefetch_related('permissions').all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]


class UserDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def get(self, request, pk):
        user = get_object_or_404(User.objects.prefetch_related('groups'), pk=pk)
        return Response(UserDetailSerializer(user).data)


class UserGroupsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        group_ids = request.data.get('groups', [])
        user.groups.set(group_ids)
        user.refresh_from_db()
        return Response({'groups': [{'id': g.id, 'name': g.name} for g in user.groups.all()]})


class ResetPasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.role == 'super_admin' and request.user.role != 'super_admin':
            return Response({'error': 'Only Super Admin can reset another Super Admin\'s password'}, status=403)
        password = User.generate_password()
        user.set_password(password)
        user.save()
        return Response({'employee_id': user.employee_id, 'password': password})


class UserGroupMappingsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def get(self, request):
        data = {}
        users = User.objects.prefetch_related('groups').only('id').all()
        for u in users:
            data[u.id] = [{'id': g.id, 'name': g.name} for g in u.groups.all()]
        return Response(data)


class RoleSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        roles = ['super_admin', 'hospital_admin', 'doctor', 'receptionist', 'patient']
        labels = {
            'super_admin': 'Super Admin',
            'hospital_admin': 'Hospital Admin',
            'doctor': 'Doctor',
            'receptionist': 'Receptionist',
            'patient': 'Patient',
        }
        icons = {
            'super_admin': '👑',
            'hospital_admin': '🏥',
            'doctor': '👨‍⚕️',
            'receptionist': '📋',
            'patient': '🙋',
        }
        descriptions = {
            'super_admin': 'Full system-wide access including all admin modules, user management, and role configuration.',
            'hospital_admin': 'Manages hospital operations — departments, doctors, slots, staff accounts, and reports.',
            'doctor': 'Access to own OPD queue, patient records, and appointment schedule. No admin access.',
            'receptionist': 'Manages OPD queue, check-in patients, issues tokens, and views doctor schedules.',
            'patient': 'Access to self-service portal for appointments, prescriptions, and medical history.',
        }

        data = []
        for role in roles:
            users_qs = User.objects.filter(role=role)
            data.append({
                'name': role,
                'label': labels.get(role, role),
                'icon': icons.get(role, '❓'),
                'description': descriptions.get(role, ''),
                'user_count': users_qs.count(),
                'is_active': users_qs.filter(is_active=True).count(),
            })
        return Response({'roles': data})


class SuperAdminStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from Patient.models import Appointment, PatientProfile
        from reception.models import Patient as ReceptionPatient, QueueEntry
        from hospital_admin.models import Department

        auth_patients = User.objects.filter(role='patient').count()
        module_patients = PatientProfile.objects.count()
        reception_patients = ReceptionPatient.objects.count()

        return Response({
            'users': {
                'total': User.objects.count(),
                'hospital_admins': User.objects.filter(role='hospital_admin').count(),
                'doctors': User.objects.filter(role='doctor').count(),
                'receptionists': User.objects.filter(role='receptionist').count(),
                'patients': auth_patients,
                'active': User.objects.filter(is_active=True).count(),
            },
            'modules': {
                'patients': max(auth_patients, module_patients, reception_patients),
                'patient_profiles': module_patients,
                'reception_patients': reception_patients,
                'doctors': Doctor.objects.filter(is_active=True).count(),
                'departments': Department.objects.filter(is_active=True).count(),
                'opd_queue_entries': QueueEntry.objects.count(),
                'appointments': Appointment.objects.count(),
            },
        })


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)[:50]


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({'status': 'ok'})


class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'updated': updated})


class ClearNotificationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        Notification.objects.filter(user=request.user).delete()
        return Response({'message': 'Notifications cleared'})


# ─── Staff / Admin Login (Employee ID + Password) ─────────────────────────


class StaffLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        employee_id = request.data.get('employee_id', '').strip()
        password = request.data.get('password', '')

        if not employee_id or not password:
            return Response({'error': 'Employee ID and password are required'}, status=400)

        user = authenticate(request, employee_id=employee_id, password=password)

        if not user:
            return Response({'error': 'Invalid Employee ID or password'}, status=401)

        if not user.is_active:
            return Response({
                'pending': True,
                'message': 'Your account is pending admin approval. Please wait for a Hospital Admin to activate your account.',
            }, status=403)

        refresh = RefreshToken.for_user(user)
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        })


class ApproveUserView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.is_active:
            return Response({'error': 'User is already active'}, status=400)
        user.is_active = True
        user.save(update_fields=['is_active'])
        Notification.send(
            user=user,
            type='account_approved',
            title='✅ Account Approved',
            message=f"Your account has been approved by {request.user.name}. You can now log in with your Employee ID.",
            icon='ti-check',
            icon_color='ni-green',
        )
        return Response(UserSerializer(user).data)


class PendingApprovalsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def get(self, request):
        users = User.objects.filter(
            is_active=False,
            role__in=['hospital_admin', 'doctor', 'receptionist'],
        ).order_by('date_joined')
        return Response(UserSerializer(users, many=True).data)


# ─── Login Page Views ─────────────────────────────────────────────────────


def staff_login_page(request):
    return render(request, 'staff-login.html')


def admin_login_page(request):
    if request.user.is_authenticated:
        if request.user.role == 'hospital_admin':
            return render(request, 'hospital-admin.html')
        if request.user.role == 'super_admin':
            return render(request, 'super-admin.html')
    return render(request, 'admin-login.html')
