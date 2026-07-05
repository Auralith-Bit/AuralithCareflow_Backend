from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render, redirect
from django.contrib.auth import views as auth_views
from django.views.static import serve as serve_static
from accounts.views import LoginView, LogoutView as CustomLogoutView
from hospital_admin import views as hospital_admin_views


def login_registration_page(request):
    return render(request, 'loginregis.html')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/reception/', include('reception.urls')),
    path('api/admin/', include('hospital_admin.urls')),

    # Serve reception, admin, and patient HTML pages
    path('reception/', include('reception.urls_page')),
    path('hospital-admin/', include('hospital_admin.urls_page')),
    path('super-admin/', include('super_admin.urls_page')),
    path('patient/', include('Patient.urls_page')),
    path('doctor/', include('doctor.urls_page')),

    # Doctor API
    path('api/doctor/', include('doctor.urls')),

    # Patient API
    path('api/patient/', include('Patient.urls')),

    # Login/Registration page
    path('login/', login_registration_page, name='login'),

    # Logout
    path('logout/', CustomLogoutView.as_view(), name='logout'),

    # API login for JWT (kept for backwards compatibility)
    path('api/login/', LoginView.as_view(), name='api_login'),
    path('', lambda request: redirect('login')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
else:
    urlpatterns += [
        re_path(
            r'^static/(?P<path>.*)$',
            serve_static,
            {'document_root': settings.STATICFILES_DIRS[0]},
        ),
    ]
