import sys
import tempfile
import types
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.core.files.storage import default_storage
from django.test import override_settings
from django.utils import timezone

from apps.assessments.tests import test_attempts_api as base
from apps.assessments.tests.helpers import create_exam_attempt
from apps.proctoring.models import ProctoringEvent, ProctoringEvidence
from apps.proctoring.services import record_event, save_snapshot


def fake_detected(wants_snapshot=False, event_type="face_missing"):
    return SimpleNamespace(
        event_type=event_type,
        occurred_at=timezone.now(),
        duration_seconds=3.5,
        confidence=0.9,
        wants_snapshot=wants_snapshot,
    )


class EventServiceTests(base.AttemptApiBase):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.enterContext(
            override_settings(
                MEDIA_ROOT=tmp.name,
                PROCTORING_EVIDENCE_RETENTION_DAYS=10,
            )
        )
        fake_adapter = types.ModuleType("apps.proctoring.vision_adapter")
        fake_adapter.SEVERITY_BY_EVENT_TYPE = {
            "face_missing": "warning",
            "phone_detected": "high",
        }
        self.enterContext(
            mock.patch.dict(
                sys.modules, {"apps.proctoring.vision_adapter": fake_adapter}
            )
        )
        self.attempt = create_exam_attempt(self.ws_a, self.exam, self.student)

    def test_event_is_saved_with_severity_from_adapter(self):
        detected = fake_detected(event_type="phone_detected")
        event = record_event(self.attempt, detected)
        event.refresh_from_db()
        self.assertEqual(event.workspace_id, self.ws_a.id)
        self.assertEqual(event.attempt_id, self.attempt.id)
        self.assertEqual(event.student_id, self.student.id)
        self.assertEqual(event.event_type, "phone_detected")
        self.assertEqual(event.severity, "high")
        self.assertEqual(event.review_status, "pending")
        self.assertEqual(event.details["duration_seconds"], 3.5)
        self.assertEqual(event.details["confidence"], 0.9)

    def test_no_snapshot_when_not_requested(self):
        record_event(self.attempt, fake_detected(False), b"imagebytes")
        self.assertEqual(ProctoringEvidence.objects.count(), 0)

    def test_no_snapshot_when_no_image(self):
        record_event(self.attempt, fake_detected(True), None)
        self.assertEqual(ProctoringEvent.objects.count(), 1)
        self.assertEqual(ProctoringEvidence.objects.count(), 0)

    def test_snapshot_is_stored_when_requested(self):
        before = timezone.now()
        event = record_event(self.attempt, fake_detected(True), b"imagebytes")
        evidence = ProctoringEvidence.objects.get(event=event)
        prefix = f"proctoring/{self.ws_a.id}/{self.attempt.id}/"
        self.assertTrue(evidence.storage_key.startswith(prefix))
        self.assertTrue(evidence.storage_key.endswith(".jpg"))
        self.assertTrue(default_storage.exists(evidence.storage_key))
        self.assertEqual(evidence.file_size, len(b"imagebytes"))
        self.assertEqual(evidence.mime_type, "image/jpeg")
        self.assertEqual(evidence.workspace_id, self.ws_a.id)
        self.assertGreater(
            evidence.retention_expires_at, before + timedelta(days=9)
        )
        self.assertLess(
            evidence.retention_expires_at,
            timezone.now() + timedelta(days=11),
        )

    def test_snapshot_failure_keeps_the_event(self):
        with mock.patch(
            "apps.proctoring.services.save_snapshot",
            side_effect=OSError("disk full"),
        ):
            with self.assertLogs("apps.proctoring.services", level="ERROR"):
                event = record_event(
                    self.attempt, fake_detected(True), b"imagebytes"
                )
        self.assertTrue(ProctoringEvent.objects.filter(pk=event.pk).exists())
        self.assertEqual(ProctoringEvidence.objects.count(), 0)

    def test_unknown_mime_uses_bin_extension(self):
        event = record_event(self.attempt, fake_detected(False))
        evidence = save_snapshot(event, b"xyz", "application/octet-stream")
        self.assertTrue(evidence.storage_key.endswith(".bin"))