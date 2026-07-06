from datetime import timezone
from rest_framework import serializers
from .models import User, Notification
from django.contrib.auth.models import Group, Permission


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role', 'phone', 'employee_id', 'avatar_color', 'is_active', 'gender', 'date_of_birth', 'address']
        read_only_fields = ['id']


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['name', 'email', 'role', 'phone', 'gender', 'date_of_birth', 'address']


class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source='content_type.app_label')
    model_name = serializers.CharField(source='content_type.model')

    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'app_label', 'model_name']


class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(), many=True, required=False
    )
    permission_details = PermissionSerializer(source='permissions', many=True, read_only=True)
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'permission_details', 'user_count']

    def get_user_count(self, obj):
        return obj.user_set.count()


class UserDetailSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = UserSerializer.Meta.fields + ['groups']
        read_only_fields = UserSerializer.Meta.read_only_fields

    def get_groups(self, obj):
        return [{'id': g.id, 'name': g.name} for g in obj.groups.all()]


class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'user', 'type', 'title', 'message', 'icon', 'icon_color', 'is_read', 'created_at', 'time_ago']
        read_only_fields = ['user', 'created_at', 'time_ago']

    def get_time_ago(self, obj):
        from django.utils import timezone
        now = timezone.now()
        delta = now - obj.created_at
        if delta.days > 0:
            return f'{delta.days} day{"s" if delta.days > 1 else ""} ago'
        elif delta.seconds >= 3600:
            hrs = delta.seconds // 3600
            return f'{hrs} hour{"s" if hrs > 1 else ""} ago'
        elif delta.seconds >= 60:
            mins = delta.seconds // 60
            return f'{mins} min ago'
        else:
            return 'just now'
