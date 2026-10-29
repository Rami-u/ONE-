"""Vision proctoring package exposing the public pipeline interface and context rules."""

from .exam_context import ExamContext, resolve_subject_category
from .face_detector import (
    blur_secondary_faces,
    blur_secondary_faces_in_video,
    extract_face_bboxes,
)
from .pipeline import (
    EventBuilder,
    analyze_frame,
    analyze_frame_with_privacy,
    clear_session_state,
    finish_session,
    process_session_frame,
)

__all__ = [
    "analyze_frame",
    "analyze_frame_with_privacy",
    "EventBuilder",
    "ExamContext",
    "resolve_subject_category",
    "blur_secondary_faces",
    "blur_secondary_faces_in_video",
    "extract_face_bboxes",
    "process_session_frame",
    "clear_session_state",
    "finish_session",
]
