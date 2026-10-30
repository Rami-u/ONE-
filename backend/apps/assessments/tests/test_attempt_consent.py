from django.utils import timezone

from apps.assessments.models import ExamAttempt

from . import test_attempts_api as base


class ConsentRecordingTests(base.AttemptApiBase):
    def get_attempt(self):
        return ExamAttempt.objects.get(student=self.student, exam=self.exam)

    def start(self, consent=True):
        self.client.force_login(self.student)
        return self.client.post(
            self.start_url(), {"consent": consent}, format="json"
        )

    def test_consent_is_recorded_for_proctored_exam(self):
        self.exam.proctoring_enabled = True
        self.exam.save()
        before = timezone.now()
        response = self.start()
        self.assertEqual(response.status_code, 201)
        attempt = self.get_attempt()
        self.assertIsNotNone(attempt.consent_given_at)
        self.assertGreaterEqual(attempt.consent_given_at, before)

    def test_resume_keeps_first_consent_time(self):
        self.exam.proctoring_enabled = True
        self.exam.save()
        self.assertEqual(self.start().status_code, 201)
        first = self.get_attempt().consent_given_at
        self.assertIsNotNone(first)
        response = self.start()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.get_attempt().consent_given_at, first)

    def test_no_consent_time_without_proctoring(self):
        self.exam.proctoring_enabled = False
        self.exam.save()
        response = self.start()
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(self.get_attempt().consent_given_at)

    def test_consent_time_not_exposed_in_response(self):
        self.exam.proctoring_enabled = True
        self.exam.save()
        response = self.start()
        self.assertNotIn("consent_given_at", response.json())