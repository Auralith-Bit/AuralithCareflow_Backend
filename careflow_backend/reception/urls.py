from django.urls import path
from . import views

urlpatterns = [
    path('queue/', views.QueueListView.as_view(), name='queue-list'),
    path('queue/stats/', views.QueueStatsView.as_view(), name='queue-stats'),
    path('queue/<int:pk>/', views.QueueDetailView.as_view(), name='queue-detail'),
    path('queue/create/', views.CreateQueueEntryView.as_view(), name='queue-create'),
    path('queue/<int:pk>/status/', views.UpdateQueueStatusView.as_view(), name='queue-status'),
    path('queue/<int:pk>/cancel/', views.CancelQueueEntryView.as_view(), name='queue-cancel'),
    path('queue/<int:pk>/reschedule/', views.RescheduleQueueEntryView.as_view(), name='queue-reschedule'),
    path('patients/search/', views.PatientSearchView.as_view(), name='patient-search'),
    path('patients/check/', views.CheckExistingPatientView.as_view(), name='patient-check'),
    path('tokens/next/', views.NextTokenView.as_view(), name='token-next'),
    path('activity/', views.ActivityLogListView.as_view(), name='activity'),
    path('doctors/', views.DoctorListView.as_view(), name='reception-doctors'),
]
