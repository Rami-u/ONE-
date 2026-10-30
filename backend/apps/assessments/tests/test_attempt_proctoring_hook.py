from datetime import timedelta
from unittest import mock

from django.utils import timezone

from apps.assessments.models import ExamAttempt

from . import test_attempts_api as base

TARGET = "apps.proctoring.services.finish_proctoring_safely"


class ProctoringCloseHookTests(base.AttemptApiBase):
    def submit_url(self, attempt_id):
        return f"/api/v1/workspaces/alpha/attempts/{attempt_id}/submit/"

    def start_attempt(self, proctored):
        self.exam.proctoring_enabled = proctored
        self.exam.save()
        self.client.force_login(self.student)
        response = self.client.post(
            self.start_url(), {"consent": True}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        return ExamAttempt.objects.get(student=self.student, exam=self.exam)

    def test_submit_calls_finish_for_proctored_exam(self):
        attempt = self.start_attempt(True)
        with mock.patch(TARGET) as finish:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.submit_url(attempt.id))
        self.assertEqual(response.status_code, 200)
        finish.assert_called_once_with(attempt.id)

    def test_submit_does_not_call_finish_without_proctoring(self):
        attempt = self.start_attempt(False)
        with mock.patch(TARGET) as finish:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.submit_url(attempt.id))
        self.assertEqual(response.status_code, 200)
        finish.assert_not_called()

    def test_expired_attempt_closed_on_start_calls_finish(self):
        attempt = self.start_attempt(True)
        ExamAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(hours=5)
        )
        with mock.patch(TARGET) as finish:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(
                    self.start_url(), {"consent": True}, format="json"
                )
        finish.assert_any_call(attempt.id)

    def test_finish_failure_does_not_break_submit(self):
        attempt = self.start_attempt(True)
        with mock.patch(
            "apps.proctoring.services.finish_attempt",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertLogs("apps.proctoring.services", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(self.submit_url(attempt.id))
        self.assertEqual(response.status_code, 200)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, ExamAttempt.Status.SUBMITTED)