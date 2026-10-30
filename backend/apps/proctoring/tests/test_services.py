from datetime import timedelta

from django.utils import timezone

from apps.assessments.tests import test_attempts_api as base
from apps.assessments.tests.helpers import create_exam_attempt
from apps.proctoring.services import record_consent


class RecordConsentTests(base.AttemptApiBase):
    def make_attempt(self):
        return create_exam_attempt(self.ws_a, self.exam, self.student)

    def test_sets_time_when_empty(self):
        attempt = self.make_attempt()
        self.assertIsNone(attempt.consent_given_at)
        now = timezone.now()
        record_consent(attempt, now)
        self.assertEqual(attempt.consent_given_at, now)
        attempt.refresh_from_db()
        self.assertEqual(attempt.consent_given_at, now)

    def test_keeps_first_time_on_second_call(self):
        attempt = self.make_attempt()
        first = timezone.now()
        record_consent(attempt, first)
        record_consent(attempt, first + timedelta(minutes=5))
        attempt.refresh_from_db()
        self.assertEqual(attempt.consent_given_at, first)

    def test_stale_instance_does_not_overwrite(self):
        attempt = self.make_attempt()
        stale = type(attempt).objects.get(pk=attempt.pk)
        first = timezone.now()
        record_consent(attempt, first)
        record_consent(stale, first + timedelta(minutes=5))
        attempt.refresh_from_db()
        self.assertEqual(attempt.consent_given_at, first)