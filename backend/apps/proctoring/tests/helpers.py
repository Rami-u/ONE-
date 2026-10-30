import uuid

from django.utils import timezone

from apps.proctoring.models import ProctoringEvent, ProctoringEvidence


def create_proctoring_event(workspace, attempt, *, student=None, **fields):
    fields.setdefault("event_type", ProctoringEvent.EventType.FACE_MISSING)
    fields.setdefault("severity", ProctoringEvent.Severity.WARNING)
    fields.setdefault("occurred_at", timezone.now())
    return ProctoringEvent.objects.create(
        workspace=workspace,
        attempt=attempt,
        student=student or attempt.student,
        **fields,
    )


def create_proctoring_evidence(workspace, event, **fields):
    fields.setdefault("evidence_type", ProctoringEvidence.EvidenceType.SNAPSHOT)
    fields.setdefault(
        "storage_key", f"proctoring/{workspace.id}/{event.attempt_id}/{uuid.uuid4().hex}.jpg"
    )
    fields.setdefault("mime_type", "image/jpeg")
    fields.setdefault("file_size", 1024)
    return ProctoringEvidence.objects.create(workspace=workspace, event=event, **fields)