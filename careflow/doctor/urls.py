from django.urls import path
from . import views

urlpatterns = [
    path('queue/', views.DoctorQueueView.as_view(), name='doctor-queue'),
    path('queue/stats/', views.DoctorQueueStatsView.as_view(), name='doctor-queue-stats'),
    path('queue/call-next/', views.CallNextPatientView.as_view(), name='doctor-call-next'),
    path('queue/<int:pk>/status/', views.UpdateQueueEntryStatusView.as_view(), name='doctor-queue-status'),
    path('queue/emergency/', views.AddEmergencyTokenView.as_view(), name='doctor-emergency'),
    path('queue/reorder/', views.ReorderQueueView.as_view(), name='doctor-reorder'),
    path('patients/register/', views.RegisterPatientView.as_view(), name='doctor-register-patient'),
    path('patients/', views.PatientDirectoryView.as_view(), name='doctor-patient-directory'),
    path('vitals/<int:queue_pk>/', views.VitalsView.as_view(), name='doctor-vitals-get'),
    path('vitals/', views.VitalsView.as_view(), name='doctor-vitals-save'),
    path('notes/<int:queue_pk>/', views.ConsultationNoteView.as_view(), name='doctor-notes-get'),
    path('notes/', views.ConsultationNoteView.as_view(), name='doctor-notes-save'),
    path('refer/doctors/', views.ReferDoctorListView.as_view(), name='doctor-refer-doctors'),
    path('refer/<int:queue_pk>/', views.ReferPatientView.as_view(), name='doctor-refer-patient'),
    path('schedule/', views.DoctorScheduleView.as_view(), name='doctor-schedule'),
    path('notifications/', views.DoctorNotificationListView.as_view(), name='doctor-notifications'),
    path('notifications/clear/', views.ClearNotificationsView.as_view(), name='doctor-notifications-clear'),
    path('profile/', views.DoctorProfileView.as_view(), name='doctor-profile'),
    path('status/', views.DoctorStatusView.as_view(), name='doctor-status'),
    path('history/', views.DoctorHistoryView.as_view(), name='doctor-history'),
]
