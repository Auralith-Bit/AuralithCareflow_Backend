from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('me/', views.MeView.as_view(), name='me'),
    path('users/', views.UserListView.as_view(), name='users'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('check-phone/', views.CheckPhoneView.as_view(), name='check-phone'),
    path('send-otp/', views.SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', views.VerifyOTPView.as_view(), name='verify-otp'),
]
