from types import SimpleNamespace
import numpy as np
import pytest

from backend.vision.config import VisionConfig
from backend.vision.face_detector import select_main_face_index
from backend.vision.head_pose import extract_head_pose
from backend.vision.pipeline import InvalidFrameError, decode_image_bytes


def create_box_landmarks(min_x: float, min_y: float, max_x: float, max_y: float) -> list[SimpleNamespace]:
    """Create four corners of a rectangular landmark box."""
    return [
        SimpleNamespace(x=x, y=y)
        for x, y in ((min_x, min_y), (min_x, max_y), (max_x, min_y), (max_x, max_y))
    ]


def test_main_face_selects_largest_bbox():
    small_face = create_box_landmarks(0.1, 0.1, 0.2, 0.2)
    large_face = create_box_landmarks(0.2, 0.2, 0.8, 0.8)
    assert select_main_face_index([small_face, large_face]) == 1


def test_main_face_tie_breaks_toward_image_center():
    off_center_face = create_box_landmarks(0.0, 0.4, 0.2, 0.6)
    centered_face = create_box_landmarks(0.4, 0.4, 0.6, 0.6)
    assert select_main_face_index([off_center_face, centered_face]) == 1


def test_empty_image_raises_invalid_frame_error():
    with pytest.raises(InvalidFrameError):
        decode_image_bytes(b"")


def test_invalid_image_raises_invalid_frame_error():
    with pytest.raises(InvalidFrameError):
        decode_image_bytes(b"not an image")


def test_pose_angles_stay_within_euler_range_at_wrap():
    angle = np.deg2rad(179.9)
    rotation_3x3 = np.array([
        [1.0, 0.0, 0.0],
        [0.0, np.cos(angle), -np.sin(angle)],
        [0.0, np.sin(angle), np.cos(angle)],
    ])
    matrix = np.eye(4)
    matrix[:3, :3] = rotation_3x3

    result = extract_head_pose(SimpleNamespace(facial_transformation_matrixes=[matrix]))
    assert result["head_pitch"] is not None and -180.0 <= result["head_pitch"] <= 180.0
    assert result["head_yaw"] is not None and -180.0 <= result["head_yaw"] <= 180.0


def test_critical_warning_attempt_supports_new_and_legacy_environment_names(monkeypatch):
    monkeypatch.setenv("VISION_LOOKING_AWAY_TERMINATE_ATTEMPT", "4")
    assert VisionConfig.from_env().looking_away_critical_warning_attempt == 4

    monkeypatch.setenv("VISION_LOOKING_AWAY_CRITICAL_WARNING_ATTEMPT", "5")
    assert VisionConfig.from_env().looking_away_critical_warning_attempt == 5
