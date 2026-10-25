"""Visual calibration tool for live webcam or recorded video files."""

from dataclasses import dataclass
import sys
from typing import Any, List, Optional
import cv2
import mediapipe as mp
import numpy as np

from .face_detector import extract_face_counts
from .head_pose import (
    DEFAULT_PITCH_DOWN_THRESHOLD,
    DEFAULT_PITCH_UP_THRESHOLD,
    DEFAULT_YAW_THRESHOLD,
    extract_head_pose,
)
from .pipeline import get_landmarker

MIRROR_DISPLAY: bool = True
ANALYZE_EVERY_N_FRAMES: int = 1
KEY_LANDMARK_INDICES: tuple[int, ...] = (1, 33, 263, 61, 291, 199)

COLOR_GREEN: tuple[int, int, int] = (0, 255, 0)
COLOR_RED: tuple[int, int, int] = (0, 0, 255)
COLOR_ORANGE: tuple[int, int, int] = (0, 165, 255)
COLOR_YELLOW: tuple[int, int, int] = (0, 255, 255)
COLOR_WHITE: tuple[int, int, int] = (255, 255, 255)
COLOR_MUTED: tuple[int, int, int] = (200, 200, 200)

KEY_QUIT: int = ord("q")
KEY_ESCAPE: int = 27


@dataclass(frozen=True)
class HudTelemetry:
    """Snapshot of telemetry values to render on the calibration HUD."""

    time_seconds: float
    face_count: int
    yaw: Optional[float]
    pitch: Optional[float]
    looking_away: bool
    landmarks: list[Any]


def inspect_frame(frame_bgr: np.ndarray) -> tuple[int, Optional[float], Optional[float], bool, List[Any]]:
    """Run production detectors on a single raw BGR frame."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = get_landmarker().detect(mp_image)

    face_data = extract_face_counts(result)
    pose_data = extract_head_pose(result)

    return (
        face_data["face_count"],
        pose_data["head_yaw"],
        pose_data["head_pitch"],
        pose_data["looking_away"],
        result.face_landmarks or [],
    )


def _determine_status(face_count: int, looking_away: bool) -> tuple[str, tuple[int, int, int]]:
    """Return status message and color indicator for the HUD."""
    if face_count == 0:
        return "STATUS: FACE MISSING", COLOR_RED
    if face_count >= 2:
        return f"STATUS: MULTIPLE FACES ({face_count})", COLOR_RED
    if looking_away:
        return "STATUS: LOOKING AWAY", COLOR_ORANGE
    return "STATUS: OK", COLOR_GREEN


def draw_hud(
    frame_bgr: np.ndarray,
    telemetry_or_t_sec: float | HudTelemetry,
    face_count: Optional[int] = None,
    yaw: Optional[float] = None,
    pitch: Optional[float] = None,
    looking_away: Optional[bool] = None,
    landmarks: Optional[List[Any]] = None,
) -> np.ndarray:
    """Render facial landmarks and telemetry overlay onto the display frame."""
    if isinstance(telemetry_or_t_sec, HudTelemetry):
        telemetry = telemetry_or_t_sec
    else:
        telemetry = HudTelemetry(
            time_seconds=float(telemetry_or_t_sec),
            face_count=face_count if face_count is not None else 0,
            yaw=yaw,
            pitch=pitch,
            looking_away=bool(looking_away),
            landmarks=landmarks or [],
        )

    vis = cv2.flip(frame_bgr, 1) if MIRROR_DISPLAY else frame_bgr.copy()
    height, width = vis.shape[:2]

    for face_lms in telemetry.landmarks:
        for idx in KEY_LANDMARK_INDICES:
            point = face_lms[idx]
            pixel_x = int((1.0 - point.x) * width) if MIRROR_DISPLAY else int(point.x * width)
            pixel_y = int(point.y * height)
            cv2.circle(vis, (pixel_x, pixel_y), 4, COLOR_YELLOW, -1)

    status_text, status_color = _determine_status(
        telemetry.face_count, telemetry.looking_away
    )

    overlay = vis.copy()
    cv2.rectangle(overlay, (10, 10), (410, 165), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, vis, 0.4, 0, vis)

    font = cv2.FONT_HERSHEY_SIMPLEX
    yaw_str = f"{telemetry.yaw:+6.1f} deg" if telemetry.yaw is not None else "N/A"
    pitch_str = f"{telemetry.pitch:+6.1f} deg" if telemetry.pitch is not None else "N/A"

    cv2.putText(vis, status_text, (20, 40), font, 0.7, status_color, 2, cv2.LINE_AA)
    cv2.putText(
        vis,
        f"Time  : {telemetry.time_seconds:5.1f} s",
        (20, 70),
        font,
        0.6,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        f"Faces : {telemetry.face_count}",
        (20, 95),
        font,
        0.6,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        f"Yaw   : {yaw_str} (Thr: +/-{DEFAULT_YAW_THRESHOLD:.0f})",
        (20, 120),
        font,
        0.6,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        f"Pitch : {pitch_str} (Thr: {DEFAULT_PITCH_DOWN_THRESHOLD:.0f}/{DEFAULT_PITCH_UP_THRESHOLD:+.0f})",
        (20, 145),
        font,
        0.6,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        "Press 'q' or ESC to quit",
        (10, height - 15),
        font,
        0.5,
        COLOR_MUTED,
        1,
        cv2.LINE_AA,
    )

    return vis


def main() -> None:
    """Entry point for the visual calibration window."""
    source: int | str = sys.argv[1] if len(sys.argv) > 1 else 0
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video source: {source}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(int(ANALYZE_EVERY_N_FRAMES), 1)
    log_step = max(int(fps), 1)

    face_count, yaw, pitch, looking_away, landmarks = 0, None, None, False, []
    frame_idx = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            t_sec = frame_idx / fps
            if frame_idx % step == 0:
                face_count, yaw, pitch, looking_away, landmarks = inspect_frame(frame)
                if frame_idx % log_step == 0:
                    print(
                        f"t={t_sec:5.1f}s | faces={face_count} | "
                        f"yaw={yaw} | pitch={pitch} | away={looking_away}"
                    )

            telemetry = HudTelemetry(
                time_seconds=t_sec,
                face_count=face_count,
                yaw=yaw,
                pitch=pitch,
                looking_away=looking_away,
                landmarks=landmarks,
            )
            vis_frame = draw_hud(frame, telemetry)
            cv2.imshow("Vision Probe - Calibration Window", vis_frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (KEY_QUIT, KEY_ESCAPE):
                break
            frame_idx += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
