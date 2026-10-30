"""Vision adapter (Track B).

Connects the proctoring services to a vision backend. Only the fake
backend exists for now. It needs no extra libraries and detects nothing.
"""

from dataclasses import dataclass
from datetime import datetime

from django.conf import settings

class InvalidFrameError(ValueError):
    """Raised when the uploaded image cannot be analysed."""
@dataclass
class DetectedEvent:
    event_type: str
    occurred_at: datetime
    duration_seconds: float | None
    confidence: float | None
    wants_snapshot: bool


# Every ProctoringEvent.EventType must be listed here, or record_event
# raises KeyError. The severity values are a first guess: confirm them
# with Track A or the lead.
SEVERITY_BY_EVENT_TYPE = {
    "face_missing": "warning",
    "multiple_faces": "high",
    "looking_away": "info",
    "phone_detected": "high",
    "tab_switch": "warning",
}


class FakeVisionBackend:
    """Default backend: detects nothing, returns no events."""

    def process_frame(self, attempt, image_bytes, content_type):
        return []

    def finish(self, attempt):
        return []


def get_vision_backend():
    name = getattr(settings, "PROCTORING_VISION_BACKEND", "fake")
    if name == "fake":
        return FakeVisionBackend()
    raise NotImplementedError(f"Unknown vision backend: {name}")