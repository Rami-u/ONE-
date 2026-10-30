"""Proctoring services (Track A).

Done: record_consent, record_event, save_snapshot, process_frame,
finish_attempt, finish_proctoring_safely.

Do not import from apps.assessments.attempt_views here (circular import).
Do not import the vision package here. Only vision_adapter (Track B) may,
and it is imported inside functions.

Proposed adapter contract (to be confirmed by Track B):
    get_vision_backend() -> backend with
        backend.process_frame(attempt, image_bytes, content_type)
            -> list of DetectedEvent
        backend.finish(attempt) -> list of DetectedEvent
"""

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.assessments.models import ExamAttempt

from .models import ProctoringEvent, ProctoringEvidence

logger = logging.getLogger(__name__)

EXTENSION_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def record_consent(attempt, now):
    """Save the first consent time on the attempt.

    The time is written only if consent_given_at is still empty, so a
    resumed attempt keeps its original time. The filter makes the check and
    the write one database statement, so two parallel requests cannot
    overwrite each other.
    """
    updated = ExamAttempt.objects.filter(
        pk=attempt.pk, consent_given_at__isnull=True
    ).update(consent_given_at=now)
    if updated:
        attempt.consent_given_at = now


def _severity_for(event_type):
    # Lazy import: vision_adapter is owned by Track B.
    from .vision_adapter import SEVERITY_BY_EVENT_TYPE

    return SEVERITY_BY_EVENT_TYPE[event_type]


def _get_backend():
    # Lazy import: vision_adapter is owned by Track B.
    from .vision_adapter import get_vision_backend

    return get_vision_backend()


def save_snapshot(event, image_bytes, mime):
    """Store the image with default_storage and create its evidence row.

    The storage key is proctoring/<workspace_id>/<attempt_id>/<uuid>.<ext>.
    If the database row cannot be created, the file is deleted again.
    """
    extension = EXTENSION_BY_MIME.get(mime, "bin")
    key = (
        f"proctoring/{event.workspace_id}/{event.attempt_id}/"
        f"{uuid.uuid4().hex}.{extension}"
    )
    saved_key = default_storage.save(key, ContentFile(image_bytes))
    try:
        return ProctoringEvidence.objects.create(
            workspace_id=event.workspace_id,
            event=event,
            evidence_type=ProctoringEvidence.EvidenceType.SNAPSHOT,
            storage_key=saved_key,
            mime_type=mime,
            file_size=len(image_bytes),
            retention_expires_at=timezone.now()
            + timedelta(days=settings.PROCTORING_EVIDENCE_RETENTION_DAYS),
        )
    except Exception:
        default_storage.delete(saved_key)
        raise


def record_event(attempt, detected, image_bytes=None, mime="image/jpeg"):
    """Save one proctoring event, and a snapshot if one was asked for.

    A snapshot failure never loses the event. Only ids are logged.
    """
    event = ProctoringEvent.objects.create(
        workspace_id=attempt.workspace_id,
        attempt=attempt,
        student_id=attempt.student_id,
        event_type=detected.event_type,
        severity=_severity_for(detected.event_type),
        occurred_at=detected.occurred_at,
        details={
            "duration_seconds": detected.duration_seconds,
            "confidence": detected.confidence,
        },
    )
    if image_bytes and detected.wants_snapshot:
        try:
            save_snapshot(event, image_bytes, mime)
        except Exception:
            logger.exception(
                "Snapshot save failed for proctoring event %s", event.pk
            )
    return event


def process_frame(attempt, image_bytes, content_type):
    """Analyse one frame and save the events found. Returns how many.

    InvalidFrameError (a bad image) is not caught here: the student view
    turns it into a 400 response.
    """
    detected_list = _get_backend().process_frame(
        attempt, image_bytes, content_type
    )
    for detected in detected_list:
        record_event(attempt, detected, image_bytes, content_type)
    return len(detected_list)


def finish_attempt(attempt_id):
    """Close the vision session of an attempt and save the last events.

    Returns how many events were saved. Image bytes are not available at
    this point, so no snapshot is stored for these events.
    """
    attempt = ExamAttempt.objects.get(pk=attempt_id)
    detected_list = _get_backend().finish(attempt)
    for detected in detected_list:
        record_event(attempt, detected)
    return len(detected_list)


def finish_proctoring_safely(attempt_id):
    """Run finish_attempt and never raise. Only the attempt id is logged."""
    try:
        finish_attempt(attempt_id)
    except Exception:
        logger.exception(
            "Finishing proctoring failed for attempt %s", attempt_id
        )