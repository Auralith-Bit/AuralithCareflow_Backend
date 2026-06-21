from rest_framework import serializers
from .models import User
from django.contrib.auth.models import Group, Permission


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone', 'avatar_color', 'is_active', 'gender', 'date_of_birth', 'address']
        read_only_fields = ['id']


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'phone', 'gender', 'date_of_birth', 'address']


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
