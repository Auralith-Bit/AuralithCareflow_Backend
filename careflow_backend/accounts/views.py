import random
import time
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate, login as auth_login
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User
from .serializers import UserSerializer


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
        role = request.data.get('role', 'receptionist')

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


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        qs = User.objects.all()
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        return qs
