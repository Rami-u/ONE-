from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsApprovedStudent, WorkspaceSlugMixin
from apps.assessments.attempt_services import attempt_end_time
from apps.assessments.models import ExamAttempt

from .services import process_frame, record_event
from .student_serializers import (
    BrowserEventResponseSerializer,
    BrowserEventSerializer,
    FrameUploadResponseSerializer,
    FrameUploadSerializer,
)
from .throttles import ProctoringBrowserEventThrottle, ProctoringFrameThrottle
from .vision_adapter import DetectedEvent, InvalidFrameError


class StudentProctoringAttemptView(WorkspaceSlugMixin, APIView):
    permission_classes = [IsApprovedStudent]

    def get_attempt(self, request, attempt_id):
        attempt = (
            ExamAttempt.objects.select_related("exam")
            .filter(
                workspace=self.workspace,
                student=request.user,
                pk=attempt_id,
            )
            .first()
        )
        if attempt is None:
            raise NotFound("Attempt not found.")
        if (
            not attempt.exam.proctoring_enabled
            or attempt.status != ExamAttempt.Status.IN_PROGRESS
            or attempt_end_time(attempt) <= timezone.now()
        ):
            raise ValidationError({"detail": "This attempt is no longer active."})
        return attempt


class FrameUploadView(StudentProctoringAttemptView):
    serializer_class = FrameUploadSerializer
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ProctoringFrameThrottle]

    @extend_schema(
        summary="Upload a proctoring frame",
        request=FrameUploadSerializer,
        responses={200: FrameUploadResponseSerializer},
    )
    def post(self, request, slug, attempt_id):
        attempt = self.get_attempt(request, attempt_id)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        frame = serializer.validated_data["frame"]
        try:
            count = process_frame(attempt, frame.read(), frame.content_type)
        except InvalidFrameError as exc:
            raise ValidationError({"frame": str(exc)}) from exc
        return Response({"events_recorded": count}, status=status.HTTP_200_OK)


class BrowserEventView(StudentProctoringAttemptView):
    serializer_class = BrowserEventSerializer
    throttle_classes = [ProctoringBrowserEventThrottle]

    @extend_schema(
        summary="Record a browser proctoring event",
        request=BrowserEventSerializer,
        responses={201: BrowserEventResponseSerializer},
    )
    def post(self, request, slug, attempt_id):
        attempt = self.get_attempt(request, attempt_id)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        detected = DetectedEvent(
            event_type=serializer.validated_data["event_type"],
            occurred_at=serializer.validated_data["occurred_at"],
            duration_seconds=None,
            confidence=None,
            wants_snapshot=False,
        )
        event = record_event(attempt, detected)
        return Response({"event_id": event.pk}, status=status.HTTP_201_CREATED)
