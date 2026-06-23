from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'doctors', views.DoctorViewSet, basename='doctor')
router.register(r'holidays', views.HolidayViewSet, basename='holiday')
router.register(r'slots', views.TimeSlotViewSet, basename='timeslot')
router.register(r'emergency-closures', views.EmergencyClosureViewSet, basename='emergencyclosure')

urlpatterns = [
    path('', include(router.urls)),
    path('hospital-profile/', views.HospitalProfileView.as_view(), name='hospital-profile'),
    path('dashboard-stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
]
