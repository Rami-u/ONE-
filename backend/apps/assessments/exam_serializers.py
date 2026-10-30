from decimal import Decimal

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.courses.models import Course, Lesson

from .models import Exam

EXAM_CREATE_ONLY_FIELDS = ("course",)


class ExamSerializer(serializers.ModelSerializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.none())
    lesson = serializers.PrimaryKeyRelatedField(
        queryset=Lesson.objects.none(), required=False, allow_null=True
    )
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    duration_minutes = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )
    passing_score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        allow_null=True,
    )
    max_attempts = serializers.IntegerField(min_value=1, required=False)
    proctoring_enabled = serializers.BooleanField(required=False)
    question_count = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            "id",
            "course",
            "lesson",
            "title",
            "description",
            "duration_minutes",
            "passing_score",
            "max_attempts",
            "proctoring_enabled",
            "status",
            "published_at",
            "created_at",
            "question_count",
            "total_points",
        ]
        read_only_fields = [
            "id",
            "status",
            "published_at",
            "created_at",
            "question_count",
            "total_points",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        workspace = self.context.get("workspace")
        if workspace is not None:
            self.fields["course"].queryset = Course.objects.filter(workspace=workspace)
            self.fields["lesson"].queryset = Lesson.objects.filter(
                workspace=workspace
            ).select_related("course")

    @extend_schema_field(OpenApiTypes.INT)
    def get_question_count(self, obj):
        if hasattr(obj, "question_count_annotated"):
            return obj.question_count_annotated
        return obj.exam_questions.count()

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_total_points(self, obj):
        if hasattr(obj, "total_points_annotated"):
            total = obj.total_points_annotated
        else:
            total = Decimal("0")
            for link in obj.exam_questions.select_related("question"):
                total += link.points_override if link.points_override is not None else link.question.points
        return str((total or Decimal("0")).quantize(Decimal("0.01")))

    def validate(self, attrs):
        instance = self.instance
        if instance is not None:
            sent = [f for f in EXAM_CREATE_ONLY_FIELDS if f in self.initial_data]
            if sent:
                raise serializers.ValidationError(
                    {f: ["Cannot be changed after creation."] for f in sent}
                )

        course = attrs["course"] if "course" in attrs else getattr(instance, "course", None)
        lesson = attrs["lesson"] if "lesson" in attrs else getattr(instance, "lesson", None)
        if lesson is not None and course is not None and lesson.course_id != course.pk:
            raise serializers.ValidationError(
                {"lesson": ["The lesson must belong to the exam's course."]}
            )
        return attrs


class StudentExamCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class StudentExamSerializer(serializers.Serializer):
    """Read-only exam card for students. Never exposes questions or passing_score."""

    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    course = serializers.SerializerMethodField()
    duration_minutes = serializers.IntegerField(allow_null=True)
    max_attempts = serializers.IntegerField()
    proctoring_enabled = serializers.BooleanField()
    question_count = serializers.IntegerField(source="question_count_annotated")
    total_points = serializers.SerializerMethodField()
    attempts_used = serializers.IntegerField(source="attempts_used_annotated")
    in_progress_attempt_id = serializers.IntegerField(
        source="in_progress_attempt_id_annotated", allow_null=True
    )

    @extend_schema_field(StudentExamCourseSerializer)
    def get_course(self, obj):
        return {"id": obj.course_id, "title": obj.course.title}

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_total_points(self, obj):
        return str((obj.total_points_annotated or Decimal("0")).quantize(Decimal("0.01")))


class ExamQuestionItemSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    points_override = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("999.99"),
        required=False,
        allow_null=True,
    )


class ExamQuestionListInputSerializer(serializers.Serializer):
    questions = ExamQuestionItemSerializer(many=True, allow_empty=True)


class ExamQuestionRowSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    position = serializers.IntegerField()
    points_override = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True
    )
    points = serializers.DecimalField(max_digits=5, decimal_places=2)
    stem = serializers.CharField()
    question_type = serializers.CharField()


class ExamQuestionListOutputSerializer(serializers.Serializer):
    questions = ExamQuestionRowSerializer(many=True)