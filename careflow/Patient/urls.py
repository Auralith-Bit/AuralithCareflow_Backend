from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.PatientRegisterView.as_view(), name='patient-register'),
    path('profile/', views.PatientProfileView.as_view(), name='patient-profile'),
    path('family/', views.FamilyMemberListCreateView.as_view(), name='family-list'),
    path('family/<int:pk>/', views.FamilyMemberDetailView.as_view(), name='family-detail'),
    path('departments/', views.DepartmentListView.as_view(), name='patient-departments'),
    path('doctors/', views.DoctorPublicListView.as_view(), name='patient-doctors'),
    path('doctors/<int:pk>/', views.DoctorPublicDetailView.as_view(), name='patient-doctor-detail'),
    path('doctors/slots/', views.AvailableSlotsView.as_view(), name='patient-doctor-slots'),
    path('appointments/', views.AppointmentListCreateView.as_view(), name='patient-appointments'),
    path('appointments/<int:pk>/', views.AppointmentDetailView.as_view(), name='patient-appointment-detail'),
    path('appointments/<int:pk>/reschedule/', views.AppointmentRescheduleView.as_view(), name='patient-appointment-reschedule'),
    path('queue/status/', views.QueueStatusView.as_view(), name='patient-queue-status'),
    path('queue/doctor-list/', views.DoctorQueueListView.as_view(), name='patient-queue-doctor-list'),
    path('my-bookings/', views.MyBookingsView.as_view(), name='patient-my-bookings'),
    path('activity/', views.PatientActivityView.as_view(), name='patient-activity'),
]
