from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from .models import Course


class CourseSerializer(serializers.ModelSerializer):
    enrollment_status = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "description",
            "price",
            "is_published",
            "enrollment_status",
            "created_at",
        ]
        read_only_fields = ["id", "enrollment_status", "created_at"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_enrollment_status(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return None
        if request.user.role != User.Role.STUDENT:
            return None
        user_enrollments = getattr(obj, "user_enrollment", None)
        if user_enrollments is not None:
            return user_enrollments[0].status if user_enrollments else None
        enrollment = obj.enrollments.filter(student=request.user).first()
        return enrollment.status if enrollment else None


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "description",
            "price",
            "is_published",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
