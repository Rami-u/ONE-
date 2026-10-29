from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.courses.models import Course, Lesson

from .models import Question, Topic
from .question_validation import validate_question_content

QUESTION_CREATE_ONLY_FIELDS = ("question_type", "status")


class TopicBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "name"]
        read_only_fields = fields


class QuestionSerializer(serializers.ModelSerializer):
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.none(), required=False, allow_null=True
    )
    lesson = serializers.PrimaryKeyRelatedField(
        queryset=Lesson.objects.none(), required=False, allow_null=True
    )
    topic_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    topics = serializers.SerializerMethodField()
    stem = serializers.CharField(max_length=5000)
    points = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0.01"), max_value=Decimal("999.99")
    )
    status = serializers.ChoiceField(
        choices=[Question.Status.DRAFT, Question.Status.APPROVED],
        required=False,
        default=Question.Status.APPROVED,
    )
    options = serializers.JSONField(required=False, allow_null=True)
    correct_answer = serializers.JSONField(required=False, allow_null=True)
    explanation = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "question_type",
            "stem",
            "options",
            "correct_answer",
            "explanation",
            "difficulty",
            "points",
            "course",
            "lesson",
            "topic_ids",
            "topics",
            "status",
            "source_type",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "topics",
            "source_type",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        workspace = self.context.get("workspace")
        if workspace is not None:
            self.fields["course"].queryset = Course.objects.filter(workspace=workspace)
            self.fields["lesson"].queryset = Lesson.objects.filter(
                workspace=workspace
            ).select_related("course")

    @extend_schema_field(TopicBriefSerializer(many=True))
    def get_topics(self, obj):
        return [
            {"id": link.topic_id, "name": link.topic.name}
            for link in obj.question_topics.all()
        ]

    def validate_topic_ids(self, value):
        workspace = self.context.get("workspace")
        ids = list(dict.fromkeys(value))
        found = set(
            Topic.objects.filter(workspace=workspace, pk__in=ids).values_list("pk", flat=True)
        )
        missing = [i for i in ids if i not in found]
        if missing:
            raise serializers.ValidationError(f"Unknown topic ids: {missing}")
        return ids

    def validate(self, attrs):
        instance = self.instance
        if instance is not None:
            sent = [f for f in QUESTION_CREATE_ONLY_FIELDS if f in self.initial_data]
            if sent:
                raise serializers.ValidationError(
                    {f: ["Cannot be changed after creation."] for f in sent}
                )

        lesson = attrs["lesson"] if "lesson" in attrs else getattr(instance, "lesson", None)
        course = attrs["course"] if "course" in attrs else getattr(instance, "course", None)
        if lesson is not None:
            if course is None:
                attrs["course"] = lesson.course
            elif lesson.course_id != course.pk:
                raise serializers.ValidationError(
                    {"lesson": ["The lesson must belong to the question's course."]}
                )

        question_type = instance.question_type if instance else attrs.get("question_type")
        if instance is None or {"options", "correct_answer"} & set(attrs):
            options = attrs["options"] if "options" in attrs else getattr(instance, "options", None)
            correct = (
                attrs["correct_answer"]
                if "correct_answer" in attrs
                else getattr(instance, "correct_answer", None)
            )
            attrs["options"], attrs["correct_answer"] = validate_question_content(
                question_type, options, correct
            )
        return attrs