"""Head pose estimation (yaw, pitch, and directional classification) from MediaPipe matrices."""

from typing import Any, Literal, Optional, TypedDict
import numpy as np
from .config import DEFAULT_CONFIG

# Default angular thresholds in degrees — tuned via probe.py and evaluate.py
DEFAULT_YAW_THRESHOLD: float = DEFAULT_CONFIG.yaw_threshold
DEFAULT_PITCH_UP_THRESHOLD: float = DEFAULT_CONFIG.pitch_up_threshold
DEFAULT_PITCH_DOWN_THRESHOLD: float = DEFAULT_CONFIG.pitch_down_threshold

MIN_EULER_ANGLE_DEGREES: float = -180.0
MAX_EULER_ANGLE_DEGREES: float = 180.0
ANGLE_ROUNDING_DECIMALS: int = 2

GazeDirection = Literal["forward", "left", "right", "up", "down", "unknown"]


class HeadPoseResult(TypedDict):
    head_yaw: Optional[float]
    head_pitch: Optional[float]
    looking_away: bool
    gaze_direction: GazeDirection
    state: str
    looking_down: bool


def classify_gaze_direction(
    yaw: Optional[float],
    pitch: Optional[float],
    yaw_threshold: float = DEFAULT_YAW_THRESHOLD,
    pitch_up_threshold: float = DEFAULT_PITCH_UP_THRESHOLD,
    pitch_down_threshold: float = DEFAULT_PITCH_DOWN_THRESHOLD,
) -> GazeDirection:
    """Classify the head orientation into a discrete direction."""
    if yaw is None or pitch is None:
        return "unknown"

    # Check if within normal forward bounds
    if (
        abs(yaw) <= yaw_threshold
        and pitch_down_threshold <= pitch <= pitch_up_threshold
    ):
        return "forward"

    # Determine dominant deviation if multiple thresholds are crossed
    yaw_excess = max(0.0, abs(yaw) - yaw_threshold)
    pitch_up_excess = max(0.0, pitch - pitch_up_threshold)
    pitch_down_excess = max(0.0, pitch_down_threshold - pitch)

    # The preview is mirrored like a selfie camera. MediaPipe's yaw/pitch signs
    # describe the unmirrored camera coordinate frame, so report directions from
    # the student's point of view in the preview.
    if yaw_excess >= pitch_up_excess and yaw_excess >= pitch_down_excess and yaw_excess > 0:
        return "left" if yaw > 0 else "right"
    if pitch_down_excess >= pitch_up_excess and pitch_down_excess > 0:
        return "up"
    if pitch_up_excess > 0:
        return "down"
    return "forward"


def _is_orientation_looking_away(
    yaw: float,
    pitch: float,
    yaw_threshold: float,
    pitch_up_threshold: float,
    pitch_down_threshold: float,
) -> bool:
    """Determine whether the Euler angles exceed looking-away thresholds."""
    return (
        abs(yaw) > yaw_threshold
        or pitch > pitch_up_threshold
        or pitch < pitch_down_threshold
    )


def extract_head_pose(
    detection_result: Any,
    yaw_threshold: float = DEFAULT_YAW_THRESHOLD,
    pitch_up_threshold: float = DEFAULT_PITCH_UP_THRESHOLD,
    pitch_down_threshold: float = DEFAULT_PITCH_DOWN_THRESHOLD,
    face_index: int = 0,
) -> HeadPoseResult:
    """Compute Euler head angles (yaw, pitch) in degrees from the specified face matrix."""
    matrices = getattr(detection_result, "facial_transformation_matrixes", None)
    if not matrices:
        return {
            "head_yaw": None,
            "head_pitch": None,
            "looking_away": False,
            "gaze_direction": "unknown",
            "state": "unknown",
            "looking_down": False,
        }

    if face_index < 0 or face_index >= len(matrices):
        face_index = 0

    transformation_matrix = np.asarray(matrices[face_index], dtype=np.float64)
    rotation_3x3 = transformation_matrix[:3, :3]

    # Standard Euler angle extraction from 3x3 rotation matrix (Z-Y-X sequence)
    hypot_xy = float(np.hypot(rotation_3x3[0, 0], rotation_3x3[1, 0]))
    pitch = float(np.degrees(np.arctan2(rotation_3x3[2, 1], rotation_3x3[2, 2])))
    yaw = float(np.degrees(np.arctan2(-rotation_3x3[2, 0], hypot_xy)))

    assert (
        MIN_EULER_ANGLE_DEGREES <= yaw <= MAX_EULER_ANGLE_DEGREES
        and MIN_EULER_ANGLE_DEGREES <= pitch <= MAX_EULER_ANGLE_DEGREES
    )

    is_looking_away = _is_orientation_looking_away(
        yaw=yaw,
        pitch=pitch,
        yaw_threshold=yaw_threshold,
        pitch_up_threshold=pitch_up_threshold,
        pitch_down_threshold=pitch_down_threshold,
    )
    rounded_yaw = round(yaw, ANGLE_ROUNDING_DECIMALS)
    rounded_pitch = round(pitch, ANGLE_ROUNDING_DECIMALS)
    direction = classify_gaze_direction(
        yaw=rounded_yaw,
        pitch=rounded_pitch,
        yaw_threshold=yaw_threshold,
        pitch_up_threshold=pitch_up_threshold,
        pitch_down_threshold=pitch_down_threshold,
    )

    return {
        "head_yaw": rounded_yaw,
        "head_pitch": rounded_pitch,
        "looking_away": bool(is_looking_away),
        "gaze_direction": direction,
        "state": "normal" if direction == "forward" else direction,
        "looking_down": direction == "down",
    }
