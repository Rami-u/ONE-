from rest_framework import serializers
from .models import CourseEnrollment


class CourseEnrollResponseSerializer(serializers.Serializer):
    enrollment_id = serializers.IntegerField()
    status = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_instructions = serializers.CharField(allow_null=True, allow_blank=True)


class StudentEnrollmentListSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField(source="course.id", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = CourseEnrollment
        fields = [
            "id",
            "course_id",
            "course_title",
            "status",
            "price_at_enrollment",
            "created_at",
            "activated_at",
        ]
        read_only_fields = fields
