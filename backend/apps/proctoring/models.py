from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.workspaces.tenancy import validate_same_workspace


class ProctoringEvent(models.Model):
    class EventType(models.TextChoices):
        FACE_MISSING = "face_missing", "Face missing"
        MULTIPLE_FACES = "multiple_faces", "Multiple faces"
        LOOKING_AWAY = "looking_away", "Looking away"
        PHONE_DETECTED = "phone_detected", "Phone detected"
        TAB_SWITCH = "tab_switch", "Tab switch"

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        HIGH = "high", "High"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        DISMISSED = "dismissed", "Dismissed"
        VIOLATION = "violation", "Violation"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="proctoring_events",
    )
    attempt = models.ForeignKey(
        "assessments.ExamAttempt",
        on_delete=models.PROTECT,
        related_name="proctoring_events",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="proctoring_events",
    )
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    occurred_at = models.DateTimeField(db_index=True)
    details = models.JSONField(null=True, blank=True)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_proctoring_events",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "proctoring_events"
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(
                fields=["attempt", "occurred_at"],
                name="proctoring_event_attempt_time",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(reviewed_by__isnull=True, reviewed_at__isnull=True)
                    | Q(reviewed_by__isnull=False, reviewed_at__isnull=False)
                ),
                name="proctoring_event_review_fields_together",
            ),
        ]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "attempt", "student", "reviewed_by")
        if (
            self.attempt_id
            and self.student_id
            and self.attempt.student_id != self.student_id
        ):
            raise ValidationError(
                {"student": "Must be the student who made the attempt."}
            )

    def __str__(self):
        return f"{self.event_type} (attempt {self.attempt_id})"


class ProctoringEvidence(models.Model):
    class EvidenceType(models.TextChoices):
        SNAPSHOT = "snapshot", "Snapshot"
        VIDEO = "video", "Video"
        SCREEN = "screen", "Screen"
        AUDIO = "audio", "Audio"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="proctoring_evidence",
    )
    event = models.ForeignKey(
        ProctoringEvent,
        on_delete=models.PROTECT,
        related_name="evidence",
    )
    evidence_type = models.CharField(max_length=20, choices=EvidenceType.choices)
    storage_key = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    retention_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "proctoring_evidence"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["storage_key"],
                name="proctoring_evidence_unique_storage_key",
            ),
        ]

    def clean(self):
        super().clean()
        validate_same_workspace(self, "event")

    def __str__(self):
        return f"{self.evidence_type} (event {self.event_id})"