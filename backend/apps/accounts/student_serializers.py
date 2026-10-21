import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.workspaces.models import Workspace

from .models import User


class StudentRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=30,
    )

    def validate_email(self, value):
        return User.objects.normalize_email_address(value)

    def validate_phone(self, value):
        if value is None or not value.strip():
            return None
        if not re.fullmatch(r"\+?[0-9 ()-]+", value):
            raise serializers.ValidationError("Enter a valid contact number.")
        digit_count = sum(character.isdigit() for character in value)
        if not 6 <= digit_count <= 15:
            raise serializers.ValidationError(
                "Enter a phone number with between 6 and 15 digits."
            )
        return value

    def validate_password(self, value):
        user = User(email=self.initial_data.get("email", ""), full_name=self.initial_data.get("full_name", ""))
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value


class StudentLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        return User.objects.normalize_email_address(value)


class StudentWorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ("slug", "name")
        read_only_fields = fields


class StudentMeSerializer(serializers.ModelSerializer):
    workspace = StudentWorkspaceSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "approval_status",
            "workspace",
        )
        read_only_fields = fields


class StudentRegistrationResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    approval_status = serializers.ChoiceField(choices=User.ApprovalStatus.choices)


class StudentPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return User.objects.normalize_email_address(value)


class StudentPasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class StudentLoginResponseSerializer(StudentMeSerializer):
    pass


class StudentMessageSerializer(serializers.Serializer):
    detail = serializers.CharField()


class StudentLoginStateErrorSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=("pending_approval", "account_rejected"))
    message = serializers.CharField()
    rejection_reason = serializers.CharField(allow_null=True, required=False)


class StudentReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "approval_status",
            "rejection_reason",
            "reviewed_at",
            "date_joined",
        )
        read_only_fields = fields


class StudentRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(max_length=1000)


class StudentReviewListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = StudentReviewSerializer(many=True)


class StudentReviewConflictSerializer(serializers.Serializer):
    detail = serializers.CharField()
