import random
import time
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User
from .serializers import UserSerializer, PermissionSerializer, GroupSerializer, UserDetailSerializer
from .permissions import IsHospitalAdmin
from django.contrib.auth.models import Group, Permission


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
        auth_login(request, user)
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
        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        email = request.data.get('email', '').strip()
        role = request.data.get('role', 'patient')
        gender = request.data.get('gender', '').strip()
        date_of_birth = request.data.get('date_of_birth', None)
        address = request.data.get('address', '').strip()

        if not phone or not first_name:
            return Response({'error': 'Phone and name are required'}, status=400)
        if User.objects.filter(phone=phone).exists():
            return Response({'error': 'Phone already registered'}, status=400)

        username = f"user_{phone[-10:]}"
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
            role=role,
            gender=gender,
            date_of_birth=date_of_birth if date_of_birth else None,
            address=address,
        )
        user.set_unusable_password()
        user.save()

        refresh = RefreshToken.for_user(user)
        auth_login(request, user)
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
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def post(self, request):
        phone = request.data.get('phone', '').strip()
        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        role = request.data.get('role', '').strip().lower()

        if not phone or not first_name or role not in ('receptionist', 'doctor', 'hospital_admin'):
            return Response({'error': 'Valid phone, name, and role are required'}, status=400)
        if User.objects.filter(phone=phone).exists():
            return Response({'error': 'Phone already registered'}, status=400)

        username = f"staff_{phone[-10:]}"
        base = username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}_{suffix}"
            suffix += 1

        user = User(
            username=username,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )
        user.set_unusable_password()
        user.save()
        return Response(UserSerializer(user).data, status=201)


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
        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        phone = request.data.get('phone', '').strip()
        email = request.data.get('email', '').strip()

        if phone and phone != user.phone:
            if User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
                return Response({'error': 'Phone already in use'}, status=400)
        if not first_name:
            return Response({'error': 'Name is required'}, status=400)

        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.email = email
        user.save()
        return Response(UserSerializer(user).data)


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


class UserGroupMappingsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHospitalAdmin]

    def get(self, request):
        data = {}
        users = User.objects.prefetch_related('groups').only('id').all()
        for u in users:
            data[u.id] = [{'id': g.id, 'name': g.name} for g in u.groups.all()]
        return Response(data)
