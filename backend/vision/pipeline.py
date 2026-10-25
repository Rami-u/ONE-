"""Core vision pipeline implementing Vision Contract v1 and temporal EventBuilder."""

import hashlib
from pathlib import Path
import threading
from typing import Any, Dict, Optional, TypedDict
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import numpy as np

from .config import DEFAULT_CONFIG
from .event_builder import EventBuilder, EventRecord
from .face_detector import extract_face_counts, select_main_face_index
from .head_pose import extract_head_pose
from .phone_detector import detect_phone
from .session_store import get_session_store

MODEL_PATH: Path = Path(__file__).resolve().parent / "face_landmarker.task"
MAX_FACES: int = DEFAULT_CONFIG.num_faces

_landmarker_instance: Optional[vision.FaceLandmarker] = None
_landmarker_lock = threading.Lock()


class InvalidFrameError(ValueError):
    """An image payload is empty, too large, or cannot be decoded."""


class FrameSignals(TypedDict):
    face_count: int
    head_yaw: Optional[float]
    head_pitch: Optional[float]
    looking_away: bool
    phone_detected: bool


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


def get_landmarker() -> vision.FaceLandmarker:
    """Return a thread-safe singleton MediaPipe FaceLandmarker instance."""
    global _landmarker_instance
    if _landmarker_instance is None:
        with _landmarker_lock:
            if _landmarker_instance is None:
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


def analyze_frame(image_bytes: bytes, timestamp: float) -> FrameSignals:
    """Vision Contract v1 entry point: analyze_frame(image_bytes, timestamp) -> signals."""
    _ = timestamp  # Kept for compatibility with the Vision Contract v1 signature
    frame_bgr = decode_image_bytes(image_bytes)
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

    detection_result = get_landmarker().detect(mp_image)
    face_info = extract_face_counts(detection_result)
    main_face_idx = select_main_face_index(
        getattr(detection_result, "face_landmarks", None)
    )
    pose_info = extract_head_pose(detection_result, face_index=main_face_idx or 0)
    phone_seen = detect_phone(frame_bgr)

    return {
        "face_count": face_info["face_count"],
        "head_yaw": pose_info["head_yaw"],
        "head_pitch": pose_info["head_pitch"],
        "looking_away": pose_info["looking_away"],
        "phone_detected": phone_seen,
    }


def process_session_frame(
    session_id: int | str,
    image_bytes: bytes,
    timestamp: float,
    snapshot_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze frame and update state while holding the session's exclusive lock."""
    store = get_session_store()
    with store.session_lock(session_id, timeout_s=0.5) as acquired:
        if not acquired:
            store.record_lock_drop()
            return {
                "signals": None,
                "events": [],
                "dropped": True,
                "reason": "session_lock_timeout",
            }
        signals = analyze_frame(image_bytes, timestamp)
        builder = store.load(session_id) or EventBuilder()
        new_events = builder.update(signals, timestamp, snapshot_path=snapshot_path)
        store.save(session_id, builder)
        return {"signals": signals, "events": new_events, "dropped": False}


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
