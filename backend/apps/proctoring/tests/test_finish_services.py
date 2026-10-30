import sys
import tempfile
import types
from types import SimpleNamespace
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from apps.assessments.tests import test_attempts_api as base
from apps.assessments.tests.helpers import create_exam_attempt
from apps.proctoring.models import ProctoringEvent, ProctoringEvidence
from apps.proctoring.services import (
    finish_attempt,
    finish_proctoring_safely,
    process_frame,
)


def fake_detected(event_type="face_missing", wants_snapshot=False):
    return SimpleNamespace(
        event_type=event_type,
        occurred_at=timezone.now(),
        duration_seconds=2.0,
        confidence=0.8,
        wants_snapshot=wants_snapshot,
    )


class FakeBackend:
    def __init__(self, frame_events=(), finish_events=()):
        self.frame_events = list(frame_events)
        self.finish_events = list(finish_events)
        self.frame_calls = []
        self.finish_calls = []

    def process_frame(self, attempt, image_bytes, content_type):
        self.frame_calls.append((attempt.pk, image_bytes, content_type))
        return self.frame_events

    def finish(self, attempt):
        self.finish_calls.append(attempt.pk)
        return self.finish_events


class FinishServiceTests(base.AttemptApiBase):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=tmp.name))
        self.backend = FakeBackend()
        adapter = types.ModuleType("apps.proctoring.vision_adapter")
        adapter.SEVERITY_BY_EVENT_TYPE = {
            "face_missing": "warning",
            "phone_detected": "high",
        }
        adapter.get_vision_backend = lambda: self.backend
        self.enterContext(
            mock.patch.dict(
                sys.modules, {"apps.proctoring.vision_adapter": adapter}
            )
        )
        self.attempt = create_exam_attempt(self.ws_a, self.exam, self.student)

    def test_process_frame_saves_events_and_returns_count(self):
        self.backend.frame_events = [
            fake_detected("face_missing"),
            fake_detected("phone_detected"),
        ]
        count = process_frame(self.attempt, b"img", "image/jpeg")
        self.assertEqual(count, 2)
        self.assertEqual(ProctoringEvent.objects.count(), 2)
        self.assertEqual(
            self.backend.frame_calls, [(self.attempt.pk, b"img", "image/jpeg")]
        )

    def test_process_frame_with_no_events_returns_zero(self):
        self.assertEqual(process_frame(self.attempt, b"img", "image/jpeg"), 0)
        self.assertEqual(ProctoringEvent.objects.count(), 0)

    def test_process_frame_stores_snapshot_when_wanted(self):
        self.backend.frame_events = [fake_detected(wants_snapshot=True)]
        process_frame(self.attempt, b"img", "image/jpeg")
        self.assertEqual(ProctoringEvidence.objects.count(), 1)

    def test_process_frame_lets_bad_frame_error_pass(self):
        def boom(attempt, image_bytes, content_type):
            raise ValueError("bad image")

        self.backend.process_frame = boom
        with self.assertRaises(ValueError):
            process_frame(self.attempt, b"img", "image/jpeg")
        self.assertEqual(ProctoringEvent.objects.count(), 0)

    def test_finish_attempt_saves_events_without_snapshot(self):
        self.backend.finish_events = [fake_detected(wants_snapshot=True)]
        count = finish_attempt(self.attempt.pk)
        self.assertEqual(count, 1)
        self.assertEqual(ProctoringEvent.objects.count(), 1)
        self.assertEqual(ProctoringEvidence.objects.count(), 0)
        self.assertEqual(self.backend.finish_calls, [self.attempt.pk])

    def test_finish_safely_returns_none_on_success(self):
        self.backend.finish_events = [fake_detected()]
        self.assertIsNone(finish_proctoring_safely(self.attempt.pk))
        self.assertEqual(ProctoringEvent.objects.count(), 1)

    def test_finish_safely_swallows_backend_errors(self):
        def boom(attempt):
            raise TimeoutError("lock timeout")

        self.backend.finish = boom
        with self.assertLogs("apps.proctoring.services", level="ERROR"):
            self.assertIsNone(finish_proctoring_safely(self.attempt.pk))

    def test_finish_safely_swallows_missing_attempt(self):
        with self.assertLogs("apps.proctoring.services", level="ERROR"):
            self.assertIsNone(finish_proctoring_safely(99999999))