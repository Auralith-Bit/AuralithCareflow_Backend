from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render, redirect
from django.contrib.auth import views as auth_views
from accounts.views import LoginView, LogoutView as CustomLogoutView
from admin_panel import views as admin_views


def login_registration_page(request):
    return render(request, 'loginregis.html')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/reception/', include('reception.urls')),
    path('api/admin/', include('admin_panel.urls')),

    # Serve reception and admin HTML pages
    path('reception/', include('reception.urls_page')),
    path('admin-panel/', include('admin_panel.urls_page')),
    path('super-admin/', admin_views.super_admin_dashboard, name='super-admin'),

    # Login/Registration page
    path('login/', login_registration_page, name='login'),

    # Logout
    path('logout/', CustomLogoutView.as_view(), name='logout'),

    # API login for JWT (kept for backwards compatibility)
    path('api/login/', LoginView.as_view(), name='api_login'),

    path('', lambda request: redirect('login')),
] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else '/static/')
