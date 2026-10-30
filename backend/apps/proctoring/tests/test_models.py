from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.tests.helpers import create_student, create_teacher, create_workspace
from apps.assessments.tests.helpers import create_exam, create_exam_attempt
from apps.courses.tests.helpers import create_course
from apps.proctoring.models import ProctoringEvent, ProctoringEvidence
from apps.proctoring.tests.helpers import create_proctoring_event, create_proctoring_evidence


class ProctoringModelTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.workspace = create_workspace("proctoring-models")
        cls.other_workspace = create_workspace("other-proctoring-models")
        cls.course = create_course(cls.workspace)
        cls.foreign_course = create_course(cls.other_workspace)
        cls.teacher = create_teacher(cls.workspace)
        cls.foreign_teacher = create_teacher(cls.other_workspace)
        cls.student = create_student(cls.workspace)
        cls.second_student = create_student(cls.workspace, email="second@example.com")
        cls.foreign_student = create_student(cls.other_workspace)
        cls.exam = create_exam(cls.workspace, cls.course)
        cls.foreign_exam = create_exam(cls.other_workspace, cls.foreign_course)
        cls.attempt = create_exam_attempt(cls.workspace, cls.exam, cls.student)
        cls.foreign_attempt = create_exam_attempt(
            cls.other_workspace, cls.foreign_exam, cls.foreign_student
        )
        cls.event = create_proctoring_event(cls.workspace, cls.attempt)
        cls.foreign_event = create_proctoring_event(cls.other_workspace, cls.foreign_attempt)

    def _new_event(self, **fields):
        values = {
            "workspace": self.workspace,
            "attempt": self.attempt,
            "student": self.student,
            "event_type": ProctoringEvent.EventType.FACE_MISSING,
            "severity": ProctoringEvent.Severity.WARNING,
            "occurred_at": timezone.now(),
        }
        values.update(fields)
        return ProctoringEvent(**values)

    # ProctoringEvent.clean()

    def test_event_defaults_to_pending_and_unreviewed(self):
        self.assertEqual(self.event.review_status, ProctoringEvent.ReviewStatus.PENDING)
        self.assertIsNone(self.event.reviewed_by)
        self.assertIsNone(self.event.reviewed_at)

    def test_event_accepts_same_workspace_relations(self):
        event = self._new_event(reviewed_by=self.teacher, reviewed_at=timezone.now())
        event.full_clean()

    def test_event_rejects_cross_workspace_attempt(self):
        event = self._new_event(attempt=self.foreign_attempt)
        with self.assertRaises(ValidationError) as caught:
            event.clean()
        self.assertEqual(set(caught.exception.message_dict), {"attempt"})

    def test_event_rejects_cross_workspace_student(self):
        event = self._new_event(student=self.foreign_student)
        with self.assertRaises(ValidationError) as caught:
            event.clean()
        self.assertEqual(set(caught.exception.message_dict), {"student"})

    def test_event_rejects_cross_workspace_reviewer(self):
        event = self._new_event(reviewed_by=self.foreign_teacher, reviewed_at=timezone.now())
        with self.assertRaises(ValidationError) as caught:
            event.clean()
        self.assertEqual(set(caught.exception.message_dict), {"reviewed_by"})

    def test_event_rejects_student_who_did_not_make_the_attempt(self):
        event = self._new_event(student=self.second_student)
        with self.assertRaises(ValidationError) as caught:
            event.clean()
        self.assertEqual(set(caught.exception.message_dict), {"student"})

    # ProctoringEvent database constraint

    def test_event_review_fields_must_be_set_together(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._new_event(reviewed_by=self.teacher, reviewed_at=None).save()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._new_event(reviewed_by=None, reviewed_at=timezone.now()).save()

    def test_event_review_fields_may_both_be_set(self):
        event = self._new_event(reviewed_by=self.teacher, reviewed_at=timezone.now())
        event.save()
        self.assertIsNotNone(event.pk)

    # Relations

    def test_attempt_exposes_events_through_related_name(self):
        self.assertEqual(list(self.attempt.proctoring_events.all()), [self.event])

    # ProctoringEvidence

    def test_evidence_accepts_same_workspace_event(self):
        evidence = create_proctoring_evidence(self.workspace, self.event)
        evidence.full_clean()

    def test_evidence_rejects_cross_workspace_event(self):
        evidence = ProctoringEvidence(
            workspace=self.workspace,
            event=self.foreign_event,
            evidence_type=ProctoringEvidence.EvidenceType.SNAPSHOT,
            storage_key="proctoring/test/cross-workspace.jpg",
        )
        with self.assertRaises(ValidationError) as caught:
            evidence.clean()
        self.assertEqual(set(caught.exception.message_dict), {"event"})

    def test_evidence_storage_key_is_unique(self):
        first = create_proctoring_evidence(self.workspace, self.event)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_proctoring_evidence(
                    self.workspace, self.event, storage_key=first.storage_key
                )