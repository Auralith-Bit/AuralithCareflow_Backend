from django.urls import path
from . import views

urlpatterns = [
    path('', views.doctor_dashboard, name='doctor-dashboard'),
]
