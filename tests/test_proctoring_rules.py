"""Tests for the new intelligent proctoring rules, warnings, face blurring, and exam context."""

from types import SimpleNamespace
import numpy as np

from backend.vision.event_builder import EventBuilder
from backend.vision.exam_context import ExamContext, resolve_subject_category
from backend.vision.face_detector import blur_secondary_faces, extract_face_bboxes
from backend.vision.head_pose import classify_gaze_direction
from backend.vision.probe import (
    COLOR_RED,
    HudTelemetry,
    _banner_text,
    _determine_status,
    _warning_counter_text,
    draw_hud,
)


def make_signals(
    face_count: int = 1,
    looking_away: bool = False,
    gaze_direction: str = "forward",
    state: str | None = None,
    looking_down: bool = False,
    head_yaw: float = 0.0,
    head_pitch: float = 0.0,
    phone_detected: bool = False,
) -> dict[str, object]:
    if state is None:
        state = "normal" if gaze_direction == "forward" else gaze_direction
    return {
        "face_count": face_count,
        "head_yaw": head_yaw,
        "head_pitch": head_pitch,
        "looking_away": looking_away,
        "state": state,
        "gaze_direction": gaze_direction,
        "looking_down": looking_down,
        "phone_detected": phone_detected,
    }


def test_non_normal_state_starts_the_five_second_looking_away_timer():
    builder = EventBuilder()
    for t in range(6):
        builder.update(
            make_signals(
                looking_away=False,
                gaze_direction="left",
                state="left",
            ),
            float(t),
        )
    assert builder.looking_away_attempts == 1
    assert builder.notifications[-1]["code"] == "LOOKING_AWAY_WARNING"
    assert builder.notifications[-1]["audio_cue"] == "warning_alarm"


def test_persistent_phone_state_warns_student_to_put_phone_down():
    builder = EventBuilder()
    builder.update(make_signals(phone_detected=True), 0.0)
    builder.update(make_signals(phone_detected=True), 4.0)
    assert builder.notifications == []
    assert builder.get_proctoring_status(4.0)["phone_detected_countdown_remaining_s"] == 1.0

    builder.update(make_signals(phone_detected=True), 5.0)
    assert builder.notifications[-1]["code"] == "PHONE_DETECTED_WARNING"
    assert builder.notifications[-1]["severity"] == "warning"
    assert builder.notifications[-1]["warning_count"] == 1
    assert builder.notifications[-1]["audio_cue"] == "phone_alarm"
    assert builder.notifications[-1]["message_ar"]
    assert not builder.exam_terminated
    builder.update(make_signals(phone_detected=False), 5.1)
    assert builder.get_proctoring_status(5.1)["phone_detected_countdown_remaining_s"] is None


def test_looking_away_state_is_red_again():
    text, color = _determine_status(1, False, state="left")
    assert text == "STATUS: LOOKING AWAY"
    assert color == COLOR_RED


def test_hud_displays_current_state_and_shared_warning_count_without_none():
    telemetry = HudTelemetry(
        time_seconds=1.0,
        face_count=1,
        yaw=35.0,
        pitch=0.0,
        looking_away=True,
        landmarks=[],
        state="right",
        warnings_count=1,
        max_warnings=3,
    )

    headline, detail = _banner_text(telemetry, "STATUS: LOOKING AWAY")
    assert headline == "STATE: LOOKING RIGHT"
    assert "None" not in headline
    assert detail == "LOOKING AWAY"
    assert _warning_counter_text(telemetry) == "Faces : 1 | Warnings: 1/3"


def test_phone_alert_hides_as_soon_as_phone_is_removed_but_counter_remains():
    telemetry = HudTelemetry(
        time_seconds=12.0,
        face_count=1,
        yaw=0.0,
        pitch=0.0,
        looking_away=False,
        landmarks=[],
        state="normal",
        warnings_count=1,
        latest_alert="PHONE_DETECTED_WARNING",
        phone_detected=False,
    )

    headline, detail = _banner_text(telemetry, "STATUS: OK (FORWARD)")
    assert headline == "STATE: NORMAL"
    assert detail == "OK (FORWARD)"
    assert _warning_counter_text(telemetry) == "Faces : 1 | Warnings: 1/3"


def test_phone_alert_remains_visible_while_phone_is_still_detected():
    telemetry = HudTelemetry(
        time_seconds=12.0,
        face_count=1,
        yaw=0.0,
        pitch=0.0,
        looking_away=False,
        landmarks=[],
        state="normal",
        warnings_count=1,
        latest_alert="PHONE_DETECTED_WARNING",
        phone_detected=True,
    )

    headline, detail = _banner_text(telemetry, "STATUS: OK (FORWARD)")
    assert headline == "WARNING 1/3 - PHONE DETECTED"
    assert detail == "STATE: NORMAL | Put the phone down now."


def test_gaze_warning_disappears_when_gaze_returns_to_normal():
    telemetry = HudTelemetry(
        time_seconds=7.0,
        face_count=1,
        yaw=0.0,
        pitch=0.0,
        looking_away=False,
        landmarks=[],
        state="normal",
        warnings_count=1,
        latest_alert="LOOKING_AWAY_WARNING",
    )

    headline, detail = _banner_text(telemetry, "STATUS: OK (FORWARD)")
    assert headline == "STATE: NORMAL"
    assert detail == "OK (FORWARD)"
    assert _warning_counter_text(telemetry) == "Faces : 1 | Warnings: 1/3"


def test_looking_away_5s_grace_two_warnings_and_third_is_critical_only():
    """Verify a 5-second grace period, two ordinary warnings, then a critical warning."""
    builder = EventBuilder()

    # Look away for only 4 seconds (< 5s grace period) -> no warning
    for t in range(0, 5):  # t = 0, 1, 2, 3, 4 (duration = 4.0s)
        builder.update(make_signals(looking_away=True, gaze_direction="left"), float(t))
    assert builder.looking_away_attempts == 0
    assert not builder.exam_terminated

    # At t = 5.0 (duration = 5.0s) -> 1st warning emitted
    events_1 = builder.update(make_signals(looking_away=True, gaze_direction="left"), 5.0)
    assert any(e["type"] == "looking_away" and e["status"] == "opened" for e in events_1)
    assert builder.looking_away_attempts == 1
    assert not builder.exam_terminated
    assert builder.notifications[-1]["code"] == "LOOKING_AWAY_WARNING"
    assert builder.notifications[-1]["remaining_attempts"] == 2
    assert builder.notifications[-1]["warning_count"] == 1

    # Return to looking forward for two frames to close the 1st run
    builder.update(make_signals(looking_away=False, gaze_direction="forward"), 6.0)
    builder.update(make_signals(looking_away=False, gaze_direction="forward"), 7.0)

    # 2nd attempt: look right from t=10 to t=15 (5 seconds) -> 2nd warning emitted
    for t in range(10, 16):
        builder.update(make_signals(looking_away=True, gaze_direction="right"), float(t))
    assert builder.looking_away_attempts == 2
    assert not builder.exam_terminated
    assert builder.notifications[-1]["code"] == "LOOKING_AWAY_WARNING"
    assert builder.notifications[-1]["remaining_attempts"] == 1
    assert builder.notifications[-1]["warning_count"] == 2

    # Return to looking forward
    builder.update(make_signals(looking_away=False, gaze_direction="forward"), 16.0)
    builder.update(make_signals(looking_away=False, gaze_direction="forward"), 17.0)

    # 3rd attempt: look up from t=20 to t=25 (5 seconds) -> critical warning, exam continues.
    for t in range(20, 26):
        builder.update(make_signals(looking_away=True, gaze_direction="up"), float(t))
    assert builder.looking_away_attempts == 3
    assert builder.exam_terminated is False
    assert builder.termination_reason is None
    assert builder.notifications[-1]["code"] == "LOOKING_AWAY_FINAL_WARNING"
    assert builder.notifications[-1]["severity"] == "critical"
    assert builder.notifications[-1]["exam_terminated"] is False
    assert builder.notifications[-1]["warning_count"] == 3
    assert "تحذير شديد" in builder.notifications[-1]["message_ar"]

    # A further incident remains a warning and does not silently close the exam.
    builder.update(make_signals(looking_away=False, gaze_direction="forward"), 26.0)
    builder.update(make_signals(looking_away=False, gaze_direction="forward"), 27.0)
    for t in range(30, 36):
        builder.update(make_signals(looking_away=True, gaze_direction="right"), float(t))
    assert builder.looking_away_attempts == 4
    assert builder.exam_terminated is False
    assert builder.notifications[-1]["code"] == "LOOKING_AWAY_FINAL_WARNING"
    assert builder.notifications[-1]["exam_terminated"] is False

    status = builder.get_proctoring_status(35.0)
    assert status["warning_count"] == 3
    assert status["max_warning_count"] == 3
    assert status["max_regular_warnings"] == 2
    assert status["critical_warning_on_attempt"] == 3


def test_multiple_faces_warns_after_five_seconds_without_terminating_exam():
    """Second face must persist for five seconds and count as a shared warning."""
    builder = EventBuilder()

    for t in range(5):
        builder.update(make_signals(face_count=2), float(t))
    assert builder.notifications == []
    assert builder.get_proctoring_status(4.0)["multiple_faces_countdown_remaining_s"] == 1.0

    builder.update(make_signals(face_count=2), 5.0)
    assert builder.notifications[-1]["code"] == "MULTIPLE_FACES_WARNING"
    assert builder.notifications[-1]["warning_count"] == 1
    assert not builder.exam_terminated

    for t in range(6, 21):
        builder.update(make_signals(face_count=2), float(t))
    assert len(builder.notifications) == 1
    assert builder.warning_count == 1
    assert not builder.exam_terminated

    builder.update(make_signals(face_count=1), 21.0)
    assert builder.get_proctoring_status(21.0)["multiple_faces_countdown_remaining_s"] is None


def test_looking_away_and_multiple_faces_share_the_same_three_warning_counter():
    builder = EventBuilder()
    for t in range(6):
        builder.update(make_signals(gaze_direction="left", state="left"), float(t))
    assert builder.notifications[-1]["warning_count"] == 1

    builder.update(make_signals(), 6.0)
    builder.update(make_signals(), 7.0)
    for t in range(10, 16):
        builder.update(make_signals(face_count=2), float(t))
    assert builder.notifications[-1]["code"] == "MULTIPLE_FACES_WARNING"
    assert builder.notifications[-1]["warning_count"] == 2

    builder.update(make_signals(face_count=1), 16.0)
    builder.update(make_signals(face_count=1), 17.0)
    builder.update(make_signals(phone_detected=True), 18.0)
    builder.update(make_signals(phone_detected=True), 23.0)
    assert builder.notifications[-1]["code"] == "PHONE_DETECTED_FINAL_WARNING"
    assert builder.notifications[-1]["warning_count"] == 3
    assert builder.notifications[-1]["severity"] == "critical"
    assert builder.exam_terminated is False


def test_blur_secondary_faces_keeps_main_student_sharp():
    """Verify secondary face pixels are blurred while primary student face stays untouched."""
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[::2, ::2] = 255

    secondary_face = [
        SimpleNamespace(x=0.05, y=0.05),
        SimpleNamespace(x=0.20, y=0.05),
        SimpleNamespace(x=0.05, y=0.20),
        SimpleNamespace(x=0.20, y=0.20),
    ]
    main_face = [
        SimpleNamespace(x=0.35, y=0.35),
        SimpleNamespace(x=0.75, y=0.35),
        SimpleNamespace(x=0.35, y=0.75),
        SimpleNamespace(x=0.75, y=0.75),
    ]

    bboxes = extract_face_bboxes([secondary_face, main_face], 200, 200)
    assert len(bboxes) == 2
    assert bboxes[0]["is_main"] is False
    assert bboxes[1]["is_main"] is True

    blurred_frame, blurred_count = blur_secondary_faces(frame, [secondary_face, main_face])
    assert blurred_count == 1

    assert np.array_equal(blurred_frame[90:130, 90:130], frame[90:130, 90:130])
    assert not np.array_equal(blurred_frame[15:35, 15:35], frame[15:35, 15:35])


def test_subject_and_question_context_rules():
    """Verify theoretical vs quantitative subjects, MCQ hand-solving, and static/formula questions."""
    for subj in ("عربي", "تاريخ", "جغرافيا", "history", "geography", "arabic"):
        assert resolve_subject_category(subj) == "theoretical"
        ctx = ExamContext(
            teacher_subject=subj,
            question_type="problem_solving",
            requires_hand_solving=True,
            teacher_solving_time_limit_s=60.0,
        )
        assert ctx.allows_extended_looking_down() is False
        assert ctx.effective_looking_down_grace_s(5.0) == 5.0

    math_problem_ctx = ExamContext(
        teacher_subject="رياضيات",
        question_type="problem_solving",
        requires_hand_solving=True,
        teacher_solving_time_limit_s=60.0,
    )
    assert math_problem_ctx.allows_extended_looking_down() is True
    assert math_problem_ctx.effective_looking_down_grace_s(5.0) == 60.0

    math_mcq_no_calc = ExamContext(
        teacher_subject="فيزياء",
        question_type="mcq",
        requires_hand_solving=False,
        teacher_solving_time_limit_s=60.0,
    )
    assert math_mcq_no_calc.allows_extended_looking_down() is False
    assert math_mcq_no_calc.effective_looking_down_grace_s(5.0) == 5.0

    math_mcq_with_calc = ExamContext(
        teacher_subject="فيزياء",
        question_type="mcq",
        requires_hand_solving=True,
        teacher_solving_time_limit_s=60.0,
    )
    assert math_mcq_with_calc.allows_extended_looking_down() is True
    assert math_mcq_with_calc.effective_looking_down_grace_s(5.0) == 60.0

    for static_qtype in ("essay", "formula_or_law", "equation_completion"):
        static_ctx = ExamContext(
            teacher_subject="فيزياء",
            question_type=static_qtype,
            requires_hand_solving=True,
            teacher_solving_time_limit_s=60.0,
        )
        assert static_ctx.allows_extended_looking_down() is False
        assert static_ctx.effective_looking_down_grace_s(5.0) == 5.0


def test_every_gaze_direction_uses_the_five_second_grace_period():
    """All non-normal states, including looking down during math, use five seconds."""
    math_ctx = ExamContext(
        teacher_subject="رياضيات",
        question_type="mcq",
        requires_hand_solving=True,
        teacher_solving_time_limit_s=60.0,
    )
    builder = EventBuilder(exam_context=math_ctx)

    for t in range(0, 5):
        builder.update(
            make_signals(
                looking_away=False,
                gaze_direction="down",
                state="down",
                looking_down=True,
                head_pitch=-35.0,
            ),
            float(t),
        )
    assert builder.looking_away_attempts == 0

    builder.update(
        make_signals(
            looking_away=False,
            gaze_direction="down",
            state="down",
            looking_down=True,
            head_pitch=-35.0,
        ),
        5.0,
    )
    assert builder.looking_away_attempts == 1
    assert "أكثر من 5 ثوانٍ" in builder.notifications[-1]["message_ar"]
    status = builder.get_proctoring_status(5.0)
    assert status["effective_looking_down_limit_s"] == 5.0
    assert status["allows_extended_looking_down"] is False

    builder.update(make_signals(looking_away=False, gaze_direction="forward"), 6.0)
    builder.update(make_signals(looking_away=False, gaze_direction="forward"), 7.0)

    for t in range(10, 16):
        builder.update(
            make_signals(
                looking_away=False,
                gaze_direction="left",
                state="left",
                looking_down=False,
                head_yaw=-40.0,
            ),
            float(t),
        )
    assert builder.looking_away_attempts == 2


def test_gaze_direction_classification():
    assert classify_gaze_direction(0.0, 0.0) == "forward"
    # Direction labels follow the student's mirrored selfie-camera view.
    assert classify_gaze_direction(-40.0, 0.0) == "right"
    assert classify_gaze_direction(40.0, 0.0) == "left"
    assert classify_gaze_direction(0.0, 35.0) == "down"
    assert classify_gaze_direction(0.0, -35.0) == "up"


def test_critical_looking_away_warning_is_prominent_in_hud():
    frame = np.zeros((300, 640, 3), dtype=np.uint8)
    telemetry = HudTelemetry(
        time_seconds=10.0,
        face_count=1,
        yaw=40.0,
        pitch=0.0,
        looking_away=True,
        landmarks=[],
        warnings_count=3,
        max_warnings=3,
        latest_alert="LOOKING_AWAY_FINAL_WARNING",
        latest_alert_severity="critical",
        state="left",
    )

    rendered = draw_hud(frame, telemetry)

    assert rendered.shape == frame.shape
    assert not np.array_equal(rendered, frame)
