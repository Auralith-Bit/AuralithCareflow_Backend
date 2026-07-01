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
    path('create-staff/', views.CreateStaffView.as_view(), name='create-staff'),
    path('users/<int:pk>/toggle-status/', views.ToggleUserStatusView.as_view(), name='toggle-user-status'),
    path('users/<int:pk>/update/', views.UpdateUserView.as_view(), name='update-user'),
    path('users/<int:pk>/delete/', views.DeleteStaffView.as_view(), name='delete-staff'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
    path('users/<int:pk>/groups/', views.UserGroupsView.as_view(), name='user-groups'),
    path('user-group-mappings/', views.UserGroupMappingsView.as_view(), name='user-group-mappings'),
    path('permissions/', views.PermissionListView.as_view(), name='permissions'),
    path('groups/', views.GroupListCreateView.as_view(), name='groups'),
    path('groups/<int:pk>/', views.GroupDetailView.as_view(), name='group-detail'),
    path('roles/', views.RoleSummaryView.as_view(), name='role-summary'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/read-all/', views.NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('notifications/clear/', views.ClearNotificationsView.as_view(), name='notifications-clear'),
]
