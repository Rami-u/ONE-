"""Local MediaPipe object detection for the COCO ``cell phone`` category."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

MODEL_PATH = Path(__file__).resolve().parent / "efficientdet_lite0_int8.tflite"
MODEL_HASH_PATH = MODEL_PATH.with_suffix(MODEL_PATH.suffix + ".sha256")
PHONE_CATEGORY = "cell phone"
PHONE_SCORE_THRESHOLD = 0.6

_detector: Optional[Any] = None
_detector_lock = threading.Lock()


def _verify_model() -> None:
    if not MODEL_PATH.is_file() or not MODEL_HASH_PATH.is_file():
        raise FileNotFoundError(
            "Phone detector model is missing. Restore backend/vision/"
            "efficientdet_lite0_int8.tflite and its .sha256 file."
        )
    expected = MODEL_HASH_PATH.read_text(encoding="ascii").strip().split()[0].lower()
    actual = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"Phone detector model SHA256 mismatch: {MODEL_PATH}")


def get_phone_detector() -> Any:
    """Create and cache the MediaPipe detector on first use."""
    global _detector
    if _detector is None:
        with _detector_lock:
            if _detector is None:
                import mediapipe as mp

                _verify_model()
                options = mp.tasks.vision.ObjectDetectorOptions(
                    base_options=mp.tasks.BaseOptions(
                        model_asset_path=str(MODEL_PATH)
                    ),
                    category_allowlist=[PHONE_CATEGORY],
                    max_results=5,
                    # Keep low-score candidates so the preview can show why a
                    # calculator or other object was considered a phone.
                    score_threshold=0.0,
                )
                _detector = mp.tasks.vision.ObjectDetector.create_from_options(options)
    return _detector


def detect_phone_details(
    frame_bgr: Any,
) -> tuple[bool, Optional[float], Optional[tuple[int, int, int, int]]]:
    """Return the threshold decision, best cell-phone score, and its image box."""
    if not isinstance(frame_bgr, np.ndarray) or frame_bgr.size == 0:
        return False, None, None
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    import mediapipe as mp

    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = get_phone_detector().detect(image)
    best_score: Optional[float] = None
    best_bbox: Optional[tuple[int, int, int, int]] = None
    for detection in result.detections:
        for category in detection.categories:
            if category.category_name != PHONE_CATEGORY:
                continue
            score = float(category.score)
            if best_score is None or score > best_score:
                box = detection.bounding_box
                best_score = score
                best_bbox = (
                    int(box.origin_x),
                    int(box.origin_y),
                    int(box.width),
                    int(box.height),
                )
    return best_score is not None and best_score >= PHONE_SCORE_THRESHOLD, best_score, best_bbox


def detect_phone(frame_bgr: Any) -> bool:
    """Return True when the local object model sees a cell phone over threshold."""
    detected, _, _ = detect_phone_details(frame_bgr)
    return detected
