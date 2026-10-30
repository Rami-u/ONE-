from rest_framework import serializers


class StartAttemptRequestSerializer(serializers.Serializer):
    consent = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Required to be true when the exam has proctoring enabled.",
    )


class ExamAttemptStateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    exam = serializers.IntegerField()
    attempt_number = serializers.IntegerField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField()
    submitted_at = serializers.DateTimeField(allow_null=True)
    ends_at = serializers.DateTimeField()
    remaining_seconds = serializers.IntegerField()
