from django.urls import path, re_path
from . import views

urlpatterns = [
    path('register/', views.PatientRegisterView.as_view(), name='patient-register'),
    path('guest-booking/', views.GuestBookingView.as_view(), name='patient-guest-booking'),
    path('profile/', views.PatientProfileView.as_view(), name='patient-profile'),
    path('family/', views.FamilyMemberListCreateView.as_view(), name='family-list'),
    path('family/<int:pk>/', views.FamilyMemberDetailView.as_view(), name='family-detail'),
    path('departments/', views.DepartmentListView.as_view(), name='patient-departments'),
    path('doctors/', views.DoctorPublicListView.as_view(), name='patient-doctors'),
    path('doctors/<int:pk>/', views.DoctorPublicDetailView.as_view(), name='patient-doctor-detail'),
    path('doctors/<int:doctor_id>/reviews/', views.DoctorReviewsView.as_view(), name='patient-doctor-reviews'),
    path('doctors/slots/', views.AvailableSlotsView.as_view(), name='patient-doctor-slots'),
    path('appointments/', views.AppointmentListCreateView.as_view(), name='patient-appointments'),
    path('appointments/<int:pk>/', views.AppointmentDetailView.as_view(), name='patient-appointment-detail'),
    path('appointments/<int:pk>/reschedule/', views.AppointmentRescheduleView.as_view(), name='patient-appointment-reschedule'),
    path('reviews/', views.DoctorReviewCreateView.as_view(), name='patient-create-review'),
    path('notifications/', views.NotificationListView.as_view(), name='patient-notifications'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='patient-notification-read'),
    path('queue/status/', views.QueueStatusView.as_view(), name='patient-queue-status'),
    path('queue/qr/', views.QueueQRView.as_view(), name='patient-queue-qr'),
    path('my-bookings/', views.MyBookingsView.as_view(), name='patient-my-bookings'),
    # Catch broken frontend URL: /my-bookings/filter=upcoming (missing ?)
    re_path(r'^my-bookings/.+', views.MyBookingsView.as_view()),
]
