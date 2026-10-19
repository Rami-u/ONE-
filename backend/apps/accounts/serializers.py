from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers

from apps.workspaces.models import Workspace

from .models import User


class TeacherCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    workspace_name = serializers.CharField(max_length=150)
    slug = serializers.CharField(max_length=63)

    def validate_email(self, value):
        return User.objects.normalize_email_address(value)

    def validate_slug(self, value):
        from apps.workspaces.validators import validate_workspace_slug

        try:
            validate_workspace_slug(value)
        except ValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if Workspace.objects.filter(slug=value).exists():
            raise serializers.ValidationError("A workspace already uses this slug.")
        return value


class TeacherSerializer(serializers.ModelSerializer):
    workspace_id = serializers.IntegerField(read_only=True)
    workspace_slug = serializers.CharField(source="workspace.slug", read_only=True)
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "full_name", "email", "role", "approval_status", "is_active",
            "workspace_id", "workspace_slug", "workspace_name", "date_joined",
        )
        read_only_fields = fields


class WorkspaceAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = (
            "id", "name", "slug", "status", "is_listed", "created_at",
        )
        read_only_fields = fields


class StaffLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        return User.objects.normalize_email_address(value)


class SetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class TeacherCreatedSerializer(serializers.Serializer):
    teacher_id = serializers.IntegerField()
    workspace_id = serializers.IntegerField()
    slug = serializers.CharField()
    invitation_sent = serializers.BooleanField()


class MessageSerializer(serializers.Serializer):
    detail = serializers.CharField()


class InvitationStatusSerializer(serializers.Serializer):
    invitation_sent = serializers.BooleanField()


class StaffLoginResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()


class TeacherListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = TeacherSerializer(many=True)
