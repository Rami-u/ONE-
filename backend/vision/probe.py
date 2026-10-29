import argparse
from dataclasses import dataclass
import platform
import time
from typing import Any, List, Optional
import cv2
import numpy as np

from .event_builder import EventBuilder
from .audio_alert import play_alarm
from .exam_context import ExamContext
from .face_detector import (
    blur_secondary_faces,
    extract_face_counts,
    select_main_face_index,
)
from .head_pose import (
    DEFAULT_PITCH_DOWN_THRESHOLD,
    DEFAULT_PITCH_UP_THRESHOLD,
    DEFAULT_YAW_THRESHOLD,
    extract_head_pose,
)
from .pipeline import get_landmarker
from .phone_detector import PHONE_SCORE_THRESHOLD, detect_phone_details

MIRROR_DISPLAY: bool = True
ANALYZE_EVERY_N_FRAMES: int = 1
KEY_LANDMARK_INDICES: tuple[int, ...] = (1, 33, 263, 61, 291, 199)

COLOR_GREEN: tuple[int, int, int] = (0, 255, 0)
COLOR_RED: tuple[int, int, int] = (0, 0, 255)
COLOR_YELLOW: tuple[int, int, int] = (0, 255, 255)
COLOR_WHITE: tuple[int, int, int] = (255, 255, 255)
COLOR_MUTED: tuple[int, int, int] = (200, 200, 200)

KEY_QUIT: int = ord("q")
KEY_ESCAPE: int = 27


@dataclass(frozen=True)
class HudTelemetry:
    time_seconds: float
    face_count: int
    yaw: Optional[float]
    pitch: Optional[float]
    looking_away: bool
    landmarks: list[Any]
    state: str = "normal"
    gaze_direction: str = "unknown"
    warnings_count: int = 0
    max_warnings: int = 3
    max_regular_warnings: int = 2
    exam_terminated: bool = False
    multiple_faces_countdown_s: Optional[float] = None
    phone_countdown_s: Optional[float] = None
    subject_label: str = "general"
    latest_alert: str = ""
    latest_alert_severity: str = "warning"
    phone_detected: bool = False
    phone_confidence: Optional[float] = None
    phone_bbox: Optional[tuple[int, int, int, int]] = None


def _open_camera_or_video(source: int | str) -> cv2.VideoCapture:
    """Open Windows webcam reliably using DirectShow/MSMF with warmup, or open video file."""
    if isinstance(source, str) and not source.isdigit():
        cap = cv2.VideoCapture(source)
        if cap.isOpened():
            return cap
        cap.release()
        raise RuntimeError(f"Could not open video file: {source}")

    preferred = int(source)
    is_win = platform.system() == "Windows"
    apis = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if is_win else [cv2.CAP_ANY]
    indices = [preferred, 1 - preferred, 2] if preferred in (0, 1) else [preferred, 0, 1]

    for idx in indices:
        for api in apis:
            cap = cv2.VideoCapture(idx, api)
            if not cap.isOpened():
                cap.release()
                continue
            for _ in range(25):
                ok, frame = cap.read()
                if ok and frame is not None and frame.size > 0:
                    print(f"[INFO] Webcam opened successfully (index={idx}, backend={api})")
                    return cap
                time.sleep(0.04)
            cap.release()

    raise RuntimeError(
        "Could not open webcam on indices 0, 1, 2. Close any browser/Zoom/camera app or check Windows camera privacy settings."
    )


def inspect_frame(
    frame_bgr: np.ndarray, blur_others: bool = True
) -> tuple[
    np.ndarray,
    int,
    Optional[float],
    Optional[float],
    bool,
    str,
    str,
    bool,
    List[Any],
    Optional[float],
    Optional[tuple[int, int, int, int]],
]:
    import mediapipe as mp

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = get_landmarker().detect(mp_image)

    landmarks = getattr(result, "face_landmarks", None) or []
    face_data = extract_face_counts(result)
    main_idx = select_main_face_index(landmarks)
    pose_data = extract_head_pose(result, face_index=main_idx or 0)
    phone_seen, phone_confidence, phone_bbox = detect_phone_details(frame_bgr)

    processed_frame = frame_bgr
    if blur_others and face_data["face_count"] >= 2:
        processed_frame, _ = blur_secondary_faces(frame_bgr, landmarks)

    main_landmarks = [landmarks[main_idx]] if (landmarks and main_idx is not None) else []

    return (
        processed_frame,
        face_data["face_count"],
        pose_data["head_yaw"],
        pose_data["head_pitch"],
        pose_data["looking_away"],
        pose_data["gaze_direction"],
        pose_data["state"],
        phone_seen,
        main_landmarks,
        phone_confidence,
        phone_bbox,
    )


def _determine_status(
    face_count: int,
    looking_away: bool,
    exam_terminated: bool = False,
    state: str = "normal",
    phone_detected: bool = False,
) -> tuple[str, tuple[int, int, int]]:
    if exam_terminated:
        return "STATUS: EXAM TERMINATED (LOCKED)", COLOR_RED
    if face_count == 0:
        return "STATUS: FACE MISSING", COLOR_RED
    if face_count >= 2:
        return f"STATUS: MULTIPLE FACES ({face_count}) - BLURRED", COLOR_RED
    if phone_detected:
        return "STATUS: PHONE DETECTED - PUT IT DOWN NOW", COLOR_RED
    if looking_away or state.strip().lower() not in {"normal", "forward"}:
        return "STATUS: LOOKING AWAY", COLOR_RED
    return "STATUS: OK (FORWARD)", COLOR_GREEN


def _current_state(face_count: int, gaze_state: str, phone_detected: bool) -> str:
    if face_count == 0:
        return "face_missing"
    if face_count >= 2:
        return "multiple_faces"
    if phone_detected:
        return "phone_detected"
    return gaze_state or "unknown"


def _state_label(state: str) -> str:
    labels = {
        "normal": "NORMAL",
        "forward": "NORMAL",
        "left": "LOOKING LEFT",
        "right": "LOOKING RIGHT",
        "up": "LOOKING UP",
        "down": "LOOKING DOWN",
        "multiple_faces": "MULTIPLE FACES",
        "face_missing": "FACE MISSING",
        "phone_detected": "PHONE DETECTED",
        "unknown": "UNKNOWN",
    }
    return labels.get(state.strip().lower(), state.replace("_", " ").upper())


def _alert_label(code: str) -> str:
    if code.startswith("LOOKING_AWAY"):
        return "LOOKING AWAY"
    if code.startswith("MULTIPLE_FACES"):
        return "MULTIPLE FACES"
    if code.startswith("PHONE_DETECTED"):
        return "PHONE DETECTED"
    return code.replace("_", " ").strip().upper()


def _alert_is_visible(telemetry: HudTelemetry) -> bool:
    if not telemetry.latest_alert:
        return False
    code = telemetry.latest_alert
    if code.startswith("PHONE_DETECTED"):
        return telemetry.phone_detected
    if code.startswith("MULTIPLE_FACES"):
        return telemetry.face_count >= 2
    if code.startswith("LOOKING_AWAY"):
        return telemetry.looking_away or telemetry.state.strip().lower() not in {
            "normal", "forward", "unknown", ""
        }
    if code.startswith("FACE_MISSING"):
        return telemetry.face_count == 0
    return True


def _banner_text(telemetry: HudTelemetry, status_text: str) -> tuple[str, str]:
    state = _state_label(telemetry.state)
    if not _alert_is_visible(telemetry):
        return f"STATE: {state}", status_text.replace("STATUS: ", "")

    severity = "CRITICAL WARNING" if telemetry.latest_alert_severity == "critical" else "WARNING"
    headline = (
        f"{severity} {telemetry.warnings_count}/{telemetry.max_warnings} "
        f"- {_alert_label(telemetry.latest_alert)}"
    )
    if telemetry.latest_alert.startswith("PHONE_DETECTED"):
        instruction = "Put the phone down now."
    elif telemetry.latest_alert.startswith("MULTIPLE_FACES"):
        instruction = "Remove the extra face from the camera."
    else:
        instruction = "Look toward the camera."
    return headline, f"STATE: {state} | {instruction}"


def _warning_counter_text(telemetry: HudTelemetry) -> str:
    return f"Faces : {telemetry.face_count} | Warnings: {telemetry.warnings_count}/{telemetry.max_warnings}"


def draw_hud(
    frame_bgr: np.ndarray,
    telemetry_or_t_sec: float | HudTelemetry,
    face_count: Optional[int] = None,
    yaw: Optional[float] = None,
    pitch: Optional[float] = None,
    looking_away: Optional[bool] = None,
    landmarks: Optional[List[Any]] = None,
) -> np.ndarray:
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

    if telemetry.phone_confidence is not None:
        dimensions = ""
        if telemetry.phone_bbox is not None:
            _, _, box_w, box_h = telemetry.phone_bbox
            dimensions = f" | box: {box_w}x{box_h}px"
        decision = "PHONE" if telemetry.phone_detected else "ignored"
        score_text = (
            f"Cell-phone candidate: {telemetry.phone_confidence:.2f}/"
            f"{PHONE_SCORE_THRESHOLD:.2f} ({decision}){dimensions}"
        )
        cv2.putText(
            vis,
            score_text,
            (20, 223),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            COLOR_WHITE,
            1,
            cv2.LINE_AA,
        )
    if telemetry.phone_detected and telemetry.phone_bbox is not None:
        box_x, box_y, box_w, box_h = telemetry.phone_bbox
        if MIRROR_DISPLAY:
            box_x = width - box_x - box_w
        box_color = COLOR_RED if telemetry.phone_detected else COLOR_MUTED
        cv2.rectangle(vis, (box_x, box_y), (box_x + box_w, box_y + box_h), box_color, 2)

    status_text, status_color = _determine_status(
        telemetry.face_count,
        telemetry.looking_away,
        telemetry.exam_terminated,
        telemetry.state,
        telemetry.phone_detected,
    )

    overlay = vis.copy()
    cv2.rectangle(overlay, (10, 10), (540, 250), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, vis, 0.4, 0, vis)

    font = cv2.FONT_HERSHEY_SIMPLEX
    yaw_str = f"{telemetry.yaw:+6.1f} deg" if telemetry.yaw is not None else "N/A"
    pitch_str = f"{telemetry.pitch:+6.1f} deg" if telemetry.pitch is not None else "N/A"

    cv2.putText(
        vis,
        f"Time  : {telemetry.time_seconds:5.1f} s | Dir: {telemetry.gaze_direction}",
        (20, 68),
        font,
        0.55,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        _warning_counter_text(telemetry),
        (20, 93),
        font,
        0.55,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        f"Yaw   : {yaw_str} (Thr: +/-{DEFAULT_YAW_THRESHOLD:.0f})",
        (20, 118),
        font,
        0.55,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        f"Pitch : {pitch_str} (Thr: {DEFAULT_PITCH_DOWN_THRESHOLD:.0f}/{DEFAULT_PITCH_UP_THRESHOLD:+.0f})",
        (20, 143),
        font,
        0.55,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        f"Context: {telemetry.subject_label}",
        (20, 168),
        font,
        0.52,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )
    if telemetry.multiple_faces_countdown_s is not None:
        cv2.putText(
            vis,
            f"Multi-face warning in: {telemetry.multiple_faces_countdown_s:4.1f} s / 5.0 s",
            (20, 198),
            font,
            0.52,
            COLOR_RED,
            2,
            cv2.LINE_AA,
        )
    elif telemetry.phone_countdown_s is not None:
        cv2.putText(
            vis,
            f"Phone warning in: {telemetry.phone_countdown_s:4.1f} s / 5.0 s",
            (20, 198),
            font,
            0.52,
            COLOR_RED,
            2,
            cv2.LINE_AA,
        )
    has_alert = _alert_is_visible(telemetry)
    alert_color = (0, 0, 180) if has_alert or status_color == COLOR_RED else (0, 95, 0)
    banner_width = min(max(width - 20, 1), 900)
    cv2.rectangle(vis, (10, 10), (10 + banner_width, 78), alert_color, -1)
    headline, subline = _banner_text(telemetry, status_text)

    cv2.putText(
        vis,
        headline,
        (22, 39),
        font,
        0.68,
        COLOR_WHITE,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        subline,
        (22, 65),
        font,
        0.48,
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


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default="0", help="Webcam index or video path")
    parser.add_argument("--subject", default="رياضيات", help="Teacher subject (e.g., رياضيات, عربي)")
    parser.add_argument(
        "--question-type",
        default="mcq",
        choices=["problem_solving", "mcq", "essay", "formula_or_law", "equation_completion"],
        help="Current question type",
    )
    parser.add_argument(
        "--hand-solving",
        action="store_true",
        help="Enable manual hand-solving allowance (for math/physics problems or MCQs needing calculation)",
    )
    parser.add_argument(
        "--solving-limit",
        type=float,
        default=60.0,
        help="Teacher's time limit (seconds) for looking down during calculation",
    )
    args = parser.parse_args(argv)

    source: int | str = int(args.source) if str(args.source).isdigit() else args.source
    cap = _open_camera_or_video(source)

    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    if fps <= 0 or fps > 120:
        fps = 20.0
    step = max(int(ANALYZE_EVERY_N_FRAMES), 1)

    exam_ctx = ExamContext(
        teacher_subject=args.subject,
        question_type=args.question_type,
        requires_hand_solving=args.hand_solving,
        teacher_solving_time_limit_s=args.solving_limit,
    )
    builder = EventBuilder(exam_context=exam_ctx)

    is_live_camera = isinstance(source, int)
    window_title = (
        "Vision Proctoring Live Camera (Press 'q' or ESC to quit)"
        if is_live_camera
        else "Vision Proctoring Video Preview (Press 'q' or ESC to quit)"
    )
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty(window_title, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    face_count, yaw, pitch, looking_away = 0, None, None, False
    gaze_dir, state, phone_seen, landmarks = "unknown", "unknown", False, []
    phone_confidence: Optional[float] = None
    phone_bbox: Optional[tuple[int, int, int, int]] = None
    frame_idx = 0
    start_wall = time.monotonic()
    print("\n========================================================")
    source_label = "Live camera" if is_live_camera else "Recorded video"
    print(f"  {source_label} preview is now open. Check your screen/taskbar.")
    print("  Press 'q' or 'ESC' inside the preview window to close.")
    print("========================================================\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            t_sec = (time.monotonic() - start_wall) if is_live_camera else (frame_idx / fps)
            display_frame = frame
            if frame_idx % step == 0:
                (
                    display_frame,
                    face_count,
                    yaw,
                    pitch,
                    looking_away,
                    gaze_dir,
                    state,
                    phone_seen,
                    landmarks,
                    phone_confidence,
                    phone_bbox,
                ) = inspect_frame(frame, blur_others=True)
                signals = {
                    "face_count": face_count,
                    "head_yaw": yaw,
                    "head_pitch": pitch,
                    "looking_away": looking_away,
                    "state": state,
                    "gaze_direction": gaze_dir,
                    "looking_down": gaze_dir == "down",
                    "phone_detected": phone_seen,
                }
                prev_notes = len(builder.notifications)
                builder.update(signals, t_sec)
                if len(builder.notifications) > prev_notes:
                    latest = builder.notifications[-1]
                    print(f"\n[ALERT @ {t_sec:.1f}s] ({latest['code']}): {latest['message_ar']}\n")
                    if not play_alarm(latest["audio_cue"]):
                        print("[AUDIO] Alarm could not play; check the default speaker/output device.")

            status_info = builder.get_proctoring_status(t_sec)
            latest_note = status_info["latest_notification"]
            latest_code = latest_note["code"] if latest_note else ""
            latest_severity = latest_note["severity"] if latest_note else "warning"
            down_limit = int(status_info["effective_looking_down_limit_s"])
            telemetry = HudTelemetry(
                time_seconds=t_sec,
                face_count=face_count,
                yaw=yaw,
                pitch=pitch,
                looking_away=looking_away,
                state=_current_state(face_count, state, phone_seen),
                landmarks=landmarks,
                gaze_direction=gaze_dir,
                warnings_count=status_info["warning_count"],
                max_warnings=status_info["max_warning_count"],
                max_regular_warnings=status_info["max_regular_warnings"],
                exam_terminated=status_info["exam_terminated"],
                multiple_faces_countdown_s=status_info["multiple_faces_countdown_remaining_s"],
                phone_countdown_s=status_info["phone_detected_countdown_remaining_s"],
                subject_label=f"Subj:{args.subject} | Q:{args.question_type} | DownLimit:{down_limit}s",
                latest_alert=latest_code,
                latest_alert_severity=latest_severity,
                phone_detected=phone_seen,
                phone_confidence=phone_confidence,
                phone_bbox=phone_bbox,
            )
            vis_frame = draw_hud(display_frame, telemetry)
            cv2.imshow(window_title, vis_frame)

            key = cv2.waitKey(1 if is_live_camera else int(1000 / fps)) & 0xFF
            if key in (KEY_QUIT, KEY_ESCAPE):
                break
            frame_idx += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
