from django.test import SimpleTestCase, override_settings

from apps.proctoring.models import ProctoringEvent
from apps.proctoring.vision_adapter import (
    SEVERITY_BY_EVENT_TYPE,
    DetectedEvent,
    FakeVisionBackend,
    get_vision_backend,
)


class SeverityTableTests(SimpleTestCase):
    def test_every_event_type_has_a_severity(self):
        for event_type in ProctoringEvent.EventType.values:
            self.assertIn(event_type, SEVERITY_BY_EVENT_TYPE)

    def test_severities_are_valid_choices(self):
        valid = set(ProctoringEvent.Severity.values)
        for severity in SEVERITY_BY_EVENT_TYPE.values():
            self.assertIn(severity, valid)


class FakeBackendTests(SimpleTestCase):
    def test_process_frame_returns_empty_list(self):
        backend = FakeVisionBackend()
        self.assertEqual(backend.process_frame(None, b"x", "image/jpeg"), [])

    def test_finish_returns_empty_list(self):
        self.assertEqual(FakeVisionBackend().finish(None), [])


class GetVisionBackendTests(SimpleTestCase):
    @override_settings(PROCTORING_VISION_BACKEND="fake")
    def test_fake_setting_returns_fake_backend(self):
        self.assertIsInstance(get_vision_backend(), FakeVisionBackend)

    @override_settings(PROCTORING_VISION_BACKEND="does-not-exist")
    def test_unknown_backend_raises(self):
        with self.assertRaises(NotImplementedError):
            get_vision_backend()


class DetectedEventTests(SimpleTestCase):
    def test_has_the_fields_services_reads(self):
        event = DetectedEvent(
            event_type="face_missing",
            occurred_at=None,
            duration_seconds=1.5,
            confidence=0.9,
            wants_snapshot=True,
        )
        self.assertEqual(event.event_type, "face_missing")
        self.assertTrue(event.wants_snapshot)