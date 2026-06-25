from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


class UserAdmin(BaseUserAdmin):
    list_display = ['id', 'name', 'phone', 'role', 'is_staff', 'is_active']
    list_filter = ['role', 'is_staff', 'is_active']
    search_fields = ['name', 'phone', 'email']
    ordering = ['name']

    fieldsets = [
        (None, {'fields': ['phone', 'password']}),
        ('Personal Info', {'fields': ['name', 'email', 'gender', 'date_of_birth', 'address']}),
        ('Permissions', {'fields': ['role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions']}),
        ('Important Dates', {'fields': ['last_login', 'date_joined']}),
    ]
    add_fieldsets = [
        (None, {
            'classes': ['wide'],
            'fields': ['phone', 'name', 'role', 'password1', 'password2'],
        }),
    ]

    readonly_fields = ['last_login', 'date_joined']


admin.site.register(User, UserAdmin)
