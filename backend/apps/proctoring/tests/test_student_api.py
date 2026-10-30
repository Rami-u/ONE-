from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.tests.helpers import create_student, create_workspace
from apps.assessments.models import Exam, ExamAttempt
from apps.courses.tests.helpers import create_course
from apps.proctoring.models import ProctoringEvent
from apps.proctoring.student_views import BrowserEventView, FrameUploadView
from apps.proctoring.throttles import (
    ProctoringBrowserEventThrottle,
    ProctoringFrameThrottle,
)
from apps.proctoring.vision_adapter import InvalidFrameError


class StudentProctoringApiTests(APITestCase):
    def setUp(self):
        self.workspace = create_workspace("alpha")
        self.other_workspace = create_workspace("beta")
        self.student = create_student(
            self.workspace,
            email="student@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.other_student = create_student(
            self.workspace,
            email="other@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.student_b = create_student(
            self.other_workspace,
            email="student-b@example.com",
            approval_status=User.ApprovalStatus.APPROVED,
        )
        course = create_course(self.workspace)
        other_course = create_course(self.other_workspace)
        exam = Exam.objects.create(
            workspace=self.workspace,
            course=course,
            title="Proctored exam",
            duration_minutes=60,
            proctoring_enabled=True,
        )
        other_exam = Exam.objects.create(
            workspace=self.other_workspace,
            course=other_course,
            title="Other exam",
            duration_minutes=60,
            proctoring_enabled=True,
        )
        self.attempt = ExamAttempt.objects.create(
            workspace=self.workspace,
            exam=exam,
            student=self.student,
            consent_given_at=timezone.now(),
        )
        self.other_attempt = ExamAttempt.objects.create(
            workspace=self.other_workspace,
            exam=other_exam,
            student=self.student_b,
        )

    def frame_url(self, attempt=None, slug="alpha"):
        attempt = attempt or self.attempt
        return f"/api/v1/workspaces/{slug}/attempts/{attempt.pk}/proctoring/frame/"

    def event_url(self, attempt=None, slug="alpha"):
        attempt = attempt or self.attempt
        return f"/api/v1/workspaces/{slug}/attempts/{attempt.pk}/proctoring/events/"

    def image_upload(self, content=b"image-bytes", name="frame.jpg", mime="image/jpeg"):
        return SimpleUploadedFile(name, content, content_type=mime)

    def test_frame_upload_calls_service_and_returns_only_count(self):
        self.client.force_login(self.student)
        with patch("apps.proctoring.student_views.process_frame", return_value=2) as process:
            response = self.client.post(
                self.frame_url(), {"frame": self.image_upload()}, format="multipart"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"events_recorded": 2})
        process.assert_called_once_with(self.attempt, b"image-bytes", "image/jpeg")

    def test_invalid_frame_error_becomes_bad_request(self):
        self.client.force_login(self.student)
        with patch(
            "apps.proctoring.student_views.process_frame",
            side_effect=InvalidFrameError("Invalid image data."),
        ):
            response = self.client.post(
                self.frame_url(), {"frame": self.image_upload()}, format="multipart"
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("frame", response.data)

    def test_frame_rejects_unsupported_type_and_oversized_upload(self):
        self.client.force_login(self.student)
        unsupported = self.client.post(
            self.frame_url(),
            {"frame": self.image_upload(mime="application/pdf", name="frame.pdf")},
            format="multipart",
        )
        self.assertEqual(unsupported.status_code, status.HTTP_400_BAD_REQUEST)

        from django.test import override_settings

        with override_settings(PROCTORING_FRAME_MAX_BYTES=2):
            oversized = self.client.post(
                self.frame_url(), {"frame": self.image_upload()}, format="multipart"
            )
        self.assertEqual(oversized.status_code, status.HTTP_400_BAD_REQUEST)

    def test_browser_event_is_recorded_and_storage_key_is_not_returned(self):
        self.client.force_login(self.student)
        response = self.client.post(
            self.event_url(), {"event_type": "tab_switch"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = ProctoringEvent.objects.get(pk=response.data["event_id"])
        self.assertEqual(event.attempt_id, self.attempt.pk)
        self.assertEqual(event.event_type, ProctoringEvent.EventType.TAB_SWITCH)
        self.assertNotIn("storage_key", response.data)

    def test_browser_event_rejects_unknown_types(self):
        self.client.force_login(self.student)
        response = self.client.post(
            self.event_url(), {"event_type": "face_missing"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attempts_are_scoped_to_workspace_and_student(self):
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.post(
                self.frame_url(self.other_attempt, slug="beta"),
                {"frame": self.image_upload()},
                format="multipart",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(
                self.event_url(self.attempt), {"event_type": "tab_switch"}, format="json"
            ).status_code,
            status.HTTP_201_CREATED,
        )
        self.client.force_login(self.other_student)
        self.assertEqual(
            self.client.post(
                self.event_url(self.attempt), {"event_type": "tab_switch"}, format="json"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(
                self.event_url(self.other_attempt, slug="alpha"),
                {"event_type": "tab_switch"},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_expired_or_finished_attempt_is_rejected(self):
        self.client.force_login(self.student)
        self.attempt.started_at = timezone.now() - timedelta(minutes=61)
        self.attempt.save(update_fields=["started_at"])
        expired = self.client.post(
            self.event_url(), {"event_type": "tab_switch"}, format="json"
        )
        self.assertEqual(expired.status_code, status.HTTP_400_BAD_REQUEST)

        self.attempt.started_at = timezone.now()
        self.attempt.status = ExamAttempt.Status.SUBMITTED
        self.attempt.save(update_fields=["started_at", "status"])
        finished = self.client.post(
            self.event_url(), {"event_type": "tab_switch"}, format="json"
        )
        self.assertEqual(finished.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unproctored_attempt_is_rejected(self):
        self.attempt.exam.proctoring_enabled = False
        self.attempt.exam.save(update_fields=["proctoring_enabled"])
        self.client.force_login(self.student)
        response = self.client.post(
            self.event_url(), {"event_type": "tab_switch"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_throttles_use_the_configured_scopes(self):
        self.assertEqual(ProctoringFrameThrottle.scope, "proctoring_frame")
        self.assertEqual(
            ProctoringBrowserEventThrottle.scope, "proctoring_browser_event"
        )
        self.assertEqual(FrameUploadView.throttle_classes, [ProctoringFrameThrottle])
        self.assertEqual(
            BrowserEventView.throttle_classes, [ProctoringBrowserEventThrottle]
        )
