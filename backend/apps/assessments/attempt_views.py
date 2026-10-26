from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import (
    IsApprovedStudent,
    IsWorkspaceMember,
    WorkspaceSlugMixin,
)

from .attempt_serializers import (
    ExamAttemptStateSerializer,
    StartAttemptRequestSerializer,
)
from .attempt_services import (
    AttemptStartError,
    attempt_end_time,
    get_exam_for_start,
    remaining_seconds,
    start_attempt,
    submit_attempt,
)
from .models import ExamAttempt


def attempt_state(attempt, now=None):
    now = now or timezone.now()
    return ExamAttemptStateSerializer(
        {
            "id": attempt.pk,
            "exam": attempt.exam_id,
            "attempt_number": attempt.attempt_number,
            "status": attempt.status,
            "started_at": attempt.started_at,
            "submitted_at": attempt.submitted_at,
            "ends_at": attempt_end_time(attempt),
            "remaining_seconds": remaining_seconds(attempt, now),
        }
    ).data


class StartAttemptView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsApprovedStudent]
    serializer_class = ExamAttemptStateSerializer

    @extend_schema(
        summary="Start or resume an exam attempt",
        description=(
            "An approved student with an active enrollment starts an attempt on a "
            "published exam in this workspace. If an unexpired attempt is already "
            "in progress it is returned (200). Consent is required when the exam "
            "has proctoring enabled."
        ),
        request=StartAttemptRequestSerializer,
        responses={
            200: ExamAttemptStateSerializer,
            201: ExamAttemptStateSerializer,
        },
    )
    def post(self, request, slug, exam_id):
        body = StartAttemptRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        exam = get_exam_for_start(self.workspace, exam_id)
        if exam is None:
            raise NotFound("Exam not found.")

        if exam.proctoring_enabled and not body.validated_data["consent"]:
            raise ValidationError(
                {"consent": "Consent is required to start this exam."}
            )

        try:
            attempt, created = start_attempt(request.user, exam, self.workspace)
        except AttemptStartError as exc:
            raise PermissionDenied(str(exc)) from exc

        if attempt is None:
            return Response(
                {"detail": "No attempts left for this exam."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            attempt_state(attempt),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SubmitAttemptView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsApprovedStudent]
    serializer_class = ExamAttemptStateSerializer

    @extend_schema(
        summary="Submit an exam attempt",
        description="The student finishes their own in-progress attempt.",
        request=None,
        responses={200: ExamAttemptStateSerializer},
    )
    def post(self, request, slug, attempt_id):
        try:
            attempt = submit_attempt(attempt_id, request.user, self.workspace)
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        if attempt is None:
            raise NotFound("Attempt not found.")
        return Response(attempt_state(attempt), status=status.HTTP_200_OK)


class AttemptDetailView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsWorkspaceMember]
    serializer_class = ExamAttemptStateSerializer

    @extend_schema(
        summary="Get an exam attempt",
        description=(
            "Status and remaining time. Students see only their own attempts; "
            "the workspace teacher can see any attempt in the workspace."
        ),
        responses={200: ExamAttemptStateSerializer},
    )
    def get(self, request, slug, attempt_id):
        queryset = ExamAttempt.objects.select_related("exam").filter(
            workspace=self.workspace, pk=attempt_id
        )
        if request.user.role == User.Role.STUDENT:
            queryset = queryset.filter(student=request.user)
        attempt = queryset.first()
        if attempt is None:
            raise NotFound("Attempt not found.")
        return Response(attempt_state(attempt), status=status.HTTP_200_OK)
