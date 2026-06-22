from django.urls import path
from . import views

urlpatterns = [
    path('', views.super_admin_dashboard, name='super-admin-dashboard'),
]
