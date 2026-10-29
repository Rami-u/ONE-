"""Core vision pipeline implementing Vision Contract v1, secondary-face blurring, and context-aware EventBuilder."""

import hashlib
from pathlib import Path
import threading
from typing import Any, Dict, Mapping, Optional, TypedDict
import cv2
import numpy as np

from .config import DEFAULT_CONFIG
from .event_builder import EventBuilder, EventRecord
from .exam_context import ExamContext
from .face_detector import (
    blur_secondary_faces,
    extract_face_bboxes,
    extract_face_counts,
    select_main_face_index,
)
from .head_pose import extract_head_pose
from .phone_detector import detect_phone
from .session_store import get_session_store

MODEL_PATH: Path = Path(__file__).resolve().parent / "face_landmarker.task"
MAX_FACES: int = DEFAULT_CONFIG.num_faces

_landmarker_instance: Optional[Any] = None
_landmarker_lock = threading.Lock()


class InvalidFrameError(ValueError):
    """An image payload is empty, too large, or cannot be decoded."""


class FrameSignals(TypedDict, total=False):
    face_count: int
    head_yaw: Optional[float]
    head_pitch: Optional[float]
    looking_away: bool
    state: str
    phone_detected: bool
    gaze_direction: str
    looking_down: bool
    main_face_index: Optional[int]
    secondary_faces_blurred: int


def _verify_model_files(model_path: Path) -> None:
    """Verify that the MediaPipe model asset and its checksum exist and match."""
    if not model_path.is_file():
        raise FileNotFoundError(f"MediaPipe model file is missing at: {model_path}")

    hash_path = model_path.with_name(model_path.name + ".sha256")
    if not hash_path.is_file():
        raise RuntimeError(
            f"Model SHA256 file is missing at: {hash_path}; run python scripts/fetch_model.py"
        )

    expected_hash = hash_path.read_text(encoding="ascii").strip().split()[0].lower()
    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise RuntimeError(f"MediaPipe model SHA256 mismatch for {model_path}")


def get_landmarker() -> Any:
    """Return a thread-safe singleton MediaPipe FaceLandmarker instance."""
    global _landmarker_instance
    if _landmarker_instance is None:
        with _landmarker_lock:
            if _landmarker_instance is None:
                import mediapipe as mp
                from mediapipe.tasks import python as mp_python
                from mediapipe.tasks.python import vision

                _verify_model_files(MODEL_PATH)
                options = vision.FaceLandmarkerOptions(
                    base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
                    running_mode=vision.RunningMode.IMAGE,
                    num_faces=MAX_FACES,
                    output_facial_transformation_matrixes=True,
                )
                _landmarker_instance = vision.FaceLandmarker.create_from_options(options)
    return _landmarker_instance


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Decode raw JPEG/PNG bytes into a bounded BGR NumPy array."""
    if not image_bytes:
        raise InvalidFrameError("Received empty image_bytes buffer.")
    if len(image_bytes) > DEFAULT_CONFIG.max_image_bytes:
        raise InvalidFrameError(
            f"Image payload exceeds {DEFAULT_CONFIG.max_image_bytes} bytes."
        )

    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    frame_bgr = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise InvalidFrameError("Invalid image_bytes: OpenCV failed to decode image.")

    height, width = frame_bgr.shape[:2]
    max_side = DEFAULT_CONFIG.max_image_side
    if max(width, height) > max_side:
        scale = max_side / float(max(width, height))
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        frame_bgr = cv2.resize(
            frame_bgr, (resized_width, resized_height), interpolation=cv2.INTER_AREA
        )

    return frame_bgr


def analyze_frame_with_privacy(
    image_bytes: bytes,
    timestamp: float,
    blur_others: bool = True,
) -> tuple[FrameSignals, Optional[bytes]]:
    """Analyze frame and return signals plus JPEG bytes with secondary faces blurred."""
    _ = timestamp
    import mediapipe as mp

    frame_bgr = decode_image_bytes(image_bytes)
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

    detection_result = get_landmarker().detect(mp_image)
    landmarks = getattr(detection_result, "face_landmarks", None)
    face_info = extract_face_counts(detection_result)
    main_face_idx = select_main_face_index(landmarks)
    pose_info = extract_head_pose(detection_result, face_index=main_face_idx or 0)
    phone_seen = detect_phone(frame_bgr)

    blurred_jpeg_bytes: Optional[bytes] = None
    blurred_count = 0
    if blur_others and face_info["face_count"] >= 2:
        blurred_bgr, blurred_count = blur_secondary_faces(frame_bgr, landmarks)
        if blurred_count > 0:
            ok, buf = cv2.imencode(".jpg", blurred_bgr)
            if ok:
                blurred_jpeg_bytes = buf.tobytes()

    signals: FrameSignals = {
        "face_count": face_info["face_count"],
        "head_yaw": pose_info["head_yaw"],
        "head_pitch": pose_info["head_pitch"],
        "looking_away": pose_info["looking_away"],
        "state": pose_info["state"],
        "phone_detected": phone_seen,
        "gaze_direction": pose_info["gaze_direction"],
        "looking_down": pose_info["looking_down"],
        "main_face_index": main_face_idx,
        "secondary_faces_blurred": blurred_count,
    }
    return signals, blurred_jpeg_bytes


def analyze_frame(image_bytes: bytes, timestamp: float) -> FrameSignals:
    """Vision Contract v1 entry point: analyze_frame(image_bytes, timestamp) -> signals."""
    signals, _ = analyze_frame_with_privacy(image_bytes, timestamp, blur_others=False)
    return {
        "face_count": signals["face_count"],
        "head_yaw": signals["head_yaw"],
        "head_pitch": signals["head_pitch"],
        "looking_away": signals["looking_away"],
        "state": signals["state"],
        "phone_detected": signals["phone_detected"],
    }


def process_session_frame(
    session_id: int | str,
    image_bytes: bytes,
    timestamp: float,
    snapshot_path: Optional[str] = None,
    exam_context: Optional[ExamContext | Mapping[str, object]] = None,
    return_blurred_frame: bool = True,
) -> Dict[str, Any]:
    """Analyze frame, blur secondary faces if present, and update proctoring state."""
    store = get_session_store()
    with store.session_lock(session_id, timeout_s=0.5) as acquired:
        if not acquired:
            store.record_lock_drop()
            return {
                "signals": None,
                "events": [],
                "notifications": [],
                "proctoring_status": None,
                "blurred_frame_bytes": None,
                "dropped": True,
                "reason": "session_lock_timeout",
            }
        signals, blurred_bytes = analyze_frame_with_privacy(
            image_bytes, timestamp, blur_others=return_blurred_frame
        )
        builder = store.load(session_id) or EventBuilder()
        if exam_context is not None:
            resolved_ctx = (
                exam_context
                if isinstance(exam_context, ExamContext)
                else ExamContext.from_dict(exam_context)
            )
            builder.set_exam_context(resolved_ctx)

        prev_note_count = len(builder.notifications)
        new_events = builder.update(signals, timestamp, snapshot_path=snapshot_path)
        new_notifications = builder.notifications[prev_note_count:]
        status = builder.get_proctoring_status(current_time=timestamp)
        store.save(session_id, builder)
        return {
            "signals": signals,
            "events": new_events,
            "notifications": new_notifications,
            "proctoring_status": status,
            "blurred_frame_bytes": blurred_bytes,
            "dropped": False,
        }


def finish_session(session_id: int | str) -> list[EventRecord]:
    """Flush lifecycle close records and release a session's state."""
    store = get_session_store()
    with store.session_lock(session_id, timeout_s=0.5) as acquired:
        if not acquired:
            raise TimeoutError(
                f"Could not finish session {session_id!r}: lock acquisition timed out"
            )
        builder = store.load(session_id)
        if builder is None:
            return []
        closed_events = builder.flush()
        store.delete(session_id)
        return closed_events


def clear_session_state(session_id: int | str) -> None:
    """Compatibility alias that flushes open events before clearing state."""
    finish_session(session_id)
