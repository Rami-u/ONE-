from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import PaymentSubmission
from .validators import validate_receipt_file


class PaymentClaimCreateSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=PaymentSubmission.Method.choices)
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=1000,
    )
    receipt_image = serializers.FileField(
        required=False,
        allow_null=True,
        validators=[validate_receipt_file],
    )


class PaymentSubmissionSerializer(serializers.ModelSerializer):
    enrollment_id = serializers.IntegerField(source="enrollment.id", read_only=True)
    course_id = serializers.IntegerField(source="enrollment.course.id", read_only=True)
    course_title = serializers.CharField(source="enrollment.course.title", read_only=True)
    student_id = serializers.IntegerField(source="submitted_by.id", read_only=True)
    student_name = serializers.CharField(source="submitted_by.full_name", read_only=True)
    student_email = serializers.EmailField(source="submitted_by.email", read_only=True)
    has_receipt = serializers.SerializerMethodField()
    reviewed_by_id = serializers.IntegerField(
        source="reviewed_by.id", read_only=True, allow_null=True
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = PaymentSubmission
        fields = [
            "id",
            "enrollment_id",
            "course_id",
            "course_title",
            "student_id",
            "student_name",
            "student_email",
            "amount",
            "method",
            "note",
            "has_receipt",
            "status",
            "submitted_at",
            "reviewed_by_id",
            "reviewed_by_name",
            "reviewed_at",
            "rejection_reason",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_has_receipt(self, obj):
        return bool(obj.receipt_image)


class PaymentRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=1000,
    )
