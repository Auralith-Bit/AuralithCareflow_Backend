from django.urls import path
from . import views

urlpatterns = [
    path('', views.patient_dashboard, name='patient-dashboard'),
]
