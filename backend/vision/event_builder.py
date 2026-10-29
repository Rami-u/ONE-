"""Time-filter per-frame vision signals into lifecycle event records and proctoring actions."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, TypedDict

from .config import DEFAULT_CONFIG
from .exam_context import ExamContext


class EventRecord(TypedDict):
    type: str
    status: str
    start_time: float
    end_time: Optional[float]
    duration: float
    confidence: float
    snapshot_path: Optional[str]
    config_version: str


class ProctoringNotification(TypedDict):
    code: str
    severity: str
    message_ar: str
    timestamp: float
    attempt_number: Optional[int]
    remaining_attempts: Optional[int]
    deadline_seconds: Optional[float]
    exam_terminated: bool
    audio_cue: str
    warning_count: int


@dataclass(frozen=True)
class Rule:
    min_duration_s: float
    predicate: Callable[[Mapping[str, object]], bool]
    tolerance_samples: int = 1
    min_samples: int = 2


def _is_non_normal_gaze_state(signals: Mapping[str, object]) -> bool:
    """Use explicit gaze state when available, retaining legacy signal compatibility."""
    state = signals.get("state")
    if state is not None:
        normalized_state = str(state).strip().lower()
        if normalized_state in {"normal", "forward", "unknown", ""}:
            return bool(signals.get("looking_away", False))
        return True
    direction = str(signals.get("gaze_direction", "unknown")).strip().lower()
    if direction not in {"", "normal", "forward", "unknown"}:
        return True
    return bool(signals.get("looking_away", False))


@dataclass
class _EventRun:
    """Internal tracking state for an active contiguous run of matching signals."""

    start_time: float
    last_match: float
    matches: int = 0
    samples: int = 0
    misses: int = 0
    opened: bool = False
    snapshot_path: Optional[str] = None
    initial_alert_sent: bool = False

    def record_match(self, timestamp: float, snapshot_path: Optional[str] = None) -> None:
        self.last_match = timestamp
        self.matches += 1
        self.samples += 1
        self.misses = 0
        if self.snapshot_path is None:
            self.snapshot_path = snapshot_path

    def record_miss(self) -> None:
        self.samples += 1
        self.misses += 1

    def meets_open_criteria(self, rule: Rule, current_time: float) -> bool:
        return (
            not self.opened
            and self.matches >= rule.min_samples
            and (current_time - self.start_time) >= rule.min_duration_s
        )

    def calculate_confidence(self) -> float:
        return self.matches / self.samples if self.samples else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "start_time": self.start_time,
            "last_match": self.last_match,
            "matches": self.matches,
            "samples": self.samples,
            "misses": self.misses,
            "opened": self.opened,
            "snapshot_path": self.snapshot_path,
            "initial_alert_sent": self.initial_alert_sent,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "_EventRun":
        return cls(
            start_time=float(data["start_time"]),
            last_match=float(data["last_match"]),
            matches=int(data["matches"]),
            samples=int(data["samples"]),
            misses=int(data["misses"]),
            opened=bool(data["opened"]),
            snapshot_path=data.get("snapshot_path"),  # type: ignore[arg-type]
            initial_alert_sent=bool(data.get("initial_alert_sent", False)),
        )


def default_rules(
    exam_context: Optional[ExamContext] = None,
    looking_away_grace_s: float = DEFAULT_CONFIG.looking_away_grace_s,
    multiple_faces_deadline_s: float = DEFAULT_CONFIG.multiple_faces_exit_deadline_s,
) -> dict[str, Rule]:
    """Construct detection rules initialized from VisionConfig and optional ExamContext."""
    _ = exam_context, multiple_faces_deadline_s
    return {
        "face_missing": Rule(
            min_duration_s=DEFAULT_CONFIG.face_missing_duration_s,
            predicate=lambda s: s["face_count"] == 0,
            tolerance_samples=DEFAULT_CONFIG.tolerance_samples,
            min_samples=DEFAULT_CONFIG.min_samples,
        ),
        "multiple_faces": Rule(
            min_duration_s=DEFAULT_CONFIG.multiple_faces_duration_s,
            predicate=lambda s: int(s["face_count"]) >= 2,  # type: ignore[arg-type]
            tolerance_samples=0,
            min_samples=DEFAULT_CONFIG.min_samples,
        ),
        "looking_away": Rule(
            min_duration_s=looking_away_grace_s,
            predicate=_is_non_normal_gaze_state,
            tolerance_samples=0,
            min_samples=DEFAULT_CONFIG.min_samples,
        ),
        "phone_detected": Rule(
            min_duration_s=DEFAULT_CONFIG.phone_detected_duration_s,
            predicate=lambda s: bool(s["phone_detected"]),
            tolerance_samples=0,
            min_samples=DEFAULT_CONFIG.min_samples,
        ),
    }


class EventBuilder:
    """Build events and enforce exam proctoring rules (warnings, strikes, blur, and context)."""

    def __init__(
        self,
        rules: Optional[dict[str, Rule]] = None,
        max_frame_gap_s: float = DEFAULT_CONFIG.max_frame_gap_s,
        config_version: str = DEFAULT_CONFIG.config_version,
        exam_context: Optional[ExamContext] = None,
        looking_away_grace_s: float = DEFAULT_CONFIG.looking_away_grace_s,
        looking_away_max_warnings: int = DEFAULT_CONFIG.looking_away_max_warnings,
        looking_away_critical_warning_attempt: int = DEFAULT_CONFIG.looking_away_critical_warning_attempt,
        multiple_faces_exit_deadline_s: float = DEFAULT_CONFIG.multiple_faces_exit_deadline_s,
    ) -> None:
        self.exam_context = exam_context or ExamContext()
        self.looking_away_grace_s = looking_away_grace_s
        self.looking_away_max_warnings = looking_away_max_warnings
        self.looking_away_critical_warning_attempt = looking_away_critical_warning_attempt
        self.multiple_faces_exit_deadline_s = multiple_faces_exit_deadline_s

        self.rules = dict(
            rules
            or default_rules(
                exam_context=self.exam_context,
                looking_away_grace_s=self.looking_away_grace_s,
                multiple_faces_deadline_s=self.multiple_faces_exit_deadline_s,
            )
        )
        self.max_frame_gap_s = max_frame_gap_s
        self.config_version = config_version
        self._runs: dict[str, _EventRun] = {}
        self._last_ts: Optional[float] = None
        self.gaps: list[tuple[float, float]] = []
        self.events: list[EventRecord] = []

        # Proctoring policy state
        self.looking_away_attempts: int = 0
        self.warning_count: int = 0
        self.exam_terminated: bool = False
        self.termination_reason: Optional[str] = None
        self.notifications: list[ProctoringNotification] = []
        self._multiple_faces_start_ts: Optional[float] = None
        self._multiple_faces_warned: bool = False
        self._multiple_faces_deadline_exceeded: bool = False

    def set_exam_context(self, exam_context: ExamContext) -> None:
        """Update the exam/question context dynamically (e.g., when moving to next question)."""
        self.exam_context = exam_context

    @property
    def completed_events(self) -> list[EventRecord]:
        """Compatibility alias for evaluators that used the old attribute."""
        return self.events

    def state_dict(self) -> dict[str, object]:
        """Return JSON-safe runtime state; predicates and rule definitions stay local."""
        return {
            "_runs": {
                event_type: run.to_dict()
                for event_type, run in self._runs.items()
            },
            "_last_ts": self._last_ts,
            "gaps": [list(gap) for gap in self.gaps],
            "events": deepcopy(self.events),
            "config_version": self.config_version,
            "exam_context": self.exam_context.to_dict(),
            "looking_away_grace_s": self.looking_away_grace_s,
            "looking_away_max_warnings": self.looking_away_max_warnings,
            "looking_away_critical_warning_attempt": self.looking_away_critical_warning_attempt,
            "multiple_faces_exit_deadline_s": self.multiple_faces_exit_deadline_s,
            "looking_away_attempts": self.looking_away_attempts,
            "warning_count": self.warning_count,
            "exam_terminated": self.exam_terminated,
            "termination_reason": self.termination_reason,
            "notifications": deepcopy(self.notifications),
            "_multiple_faces_start_ts": self._multiple_faces_start_ts,
            "_multiple_faces_warned": self._multiple_faces_warned,
            "_multiple_faces_deadline_exceeded": self._multiple_faces_deadline_exceeded,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, object],
        rules: Optional[dict[str, Rule]] = None,
        max_frame_gap_s: float = DEFAULT_CONFIG.max_frame_gap_s,
        config_version: Optional[str] = None,
    ) -> "EventBuilder":
        """Restore runtime state while recreating predicates from local code."""
        resolved_version = config_version or str(
            state.get("config_version", DEFAULT_CONFIG.config_version)
        )
        raw_context = state.get("exam_context")
        exam_context = (
            ExamContext.from_dict(raw_context)  # type: ignore[arg-type]
            if isinstance(raw_context, Mapping)
            else ExamContext()
        )
        builder = cls(
            rules=rules,
            max_frame_gap_s=max_frame_gap_s,
            config_version=resolved_version,
            exam_context=exam_context,
            looking_away_grace_s=float(
                state.get("looking_away_grace_s", DEFAULT_CONFIG.looking_away_grace_s)  # type: ignore[arg-type]
            ),
            looking_away_max_warnings=int(
                state.get("looking_away_max_warnings", DEFAULT_CONFIG.looking_away_max_warnings)  # type: ignore[arg-type]
            ),
            looking_away_critical_warning_attempt=int(
                state.get(
                    "looking_away_critical_warning_attempt",
                    state.get(
                        "looking_away_terminate_attempt",
                        DEFAULT_CONFIG.looking_away_critical_warning_attempt,
                    ),
                )  # type: ignore[arg-type]
            ),
            multiple_faces_exit_deadline_s=float(
                state.get(
                    "multiple_faces_exit_deadline_s",
                    DEFAULT_CONFIG.multiple_faces_exit_deadline_s,
                )  # type: ignore[arg-type]
            ),
        )
        raw_runs = state.get("_runs", {})
        if isinstance(raw_runs, dict):
            builder._runs = {
                event_type: _EventRun.from_dict(run_data)
                for event_type, run_data in raw_runs.items()
                if isinstance(run_data, dict)
            }
        last_ts = state.get("_last_ts")
        builder._last_ts = float(last_ts) if last_ts is not None else None
        builder.gaps = [tuple(map(float, gap)) for gap in state.get("gaps", [])]  # type: ignore[arg-type]
        builder.events = deepcopy(state.get("events", []))  # type: ignore[assignment]
        builder.looking_away_attempts = int(state.get("looking_away_attempts", 0))  # type: ignore[arg-type]
        builder.warning_count = min(
            int(state.get("warning_count", builder.looking_away_attempts)),
            builder.looking_away_critical_warning_attempt,
        )  # type: ignore[arg-type]
        builder.exam_terminated = bool(state.get("exam_terminated", False))
        term_reason = state.get("termination_reason")
        builder.termination_reason = str(term_reason) if term_reason is not None else None
        builder.notifications = deepcopy(state.get("notifications", []))  # type: ignore[assignment]
        mf_start = state.get("_multiple_faces_start_ts")
        builder._multiple_faces_start_ts = float(mf_start) if mf_start is not None else None
        builder._multiple_faces_warned = bool(state.get("_multiple_faces_warned", False))
        builder._multiple_faces_deadline_exceeded = bool(
            state.get("_multiple_faces_deadline_exceeded", False)
        )
        return builder

    def _effective_rule_for_signals(
        self, event_type: str, base_rule: Rule, signals: Mapping[str, object]
    ) -> Rule:
        """Use the same five-second grace period for every non-normal gaze state."""
        _ = event_type, signals
        return base_rule

    def _record_proctoring_warning(
        self,
        *,
        timestamp: float,
        code: str,
        critical_code: str,
        message_ar: str,
        audio_cue: str = "warning_alarm",
    ) -> None:
        """Add an incident to the shared three-warning counter."""
        warning_limit = self.looking_away_critical_warning_attempt
        self.warning_count = min(self.warning_count + 1, warning_limit)
        attempt = self.warning_count
        is_critical = attempt >= warning_limit
        remaining = max(0, warning_limit - attempt)
        note: ProctoringNotification = {
            "code": critical_code if is_critical else code,
            "severity": "critical" if is_critical else "warning",
            "message_ar": (
                f"تحذير شديد ({attempt}/{warning_limit}): {message_ar} "
                "الامتحان مستمر."
                if is_critical
                else f"تحذير ({attempt}/{warning_limit}): {message_ar}"
            ),
            "timestamp": timestamp,
            "attempt_number": attempt,
            "remaining_attempts": remaining,
            "deadline_seconds": None,
            "exam_terminated": False,
            "audio_cue": (
                audio_cue
                if audio_cue == "phone_alarm"
                else "critical_alarm" if is_critical else audio_cue
            ),
            "warning_count": attempt,
        }
        self.notifications.append(note)

    def _handle_looking_away_opened(
        self, timestamp: float, signals: Mapping[str, object]
    ) -> None:
        """Count one warning when a non-normal gaze direction lasts five seconds."""
        self.looking_away_attempts += 1
        direction = str(signals.get("gaze_direction", "غير طبيعي"))
        self._record_proctoring_warning(
            timestamp=timestamp,
            code="LOOKING_AWAY_WARNING",
            critical_code="LOOKING_AWAY_FINAL_WARNING",
            message_ar=(
                f"أنت تنظر في اتجاه {direction} منذ أكثر من "
                f"{int(self.looking_away_grace_s)} ثوانٍ. انظر إلى الكاميرا الآن."
            ),
        )

    def _handle_multiple_faces_opened(self, timestamp: float) -> None:
        """Count one shared warning after a second face stays for five seconds."""
        self._multiple_faces_warned = True
        self._record_proctoring_warning(
            timestamp=timestamp,
            code="MULTIPLE_FACES_WARNING",
            critical_code="MULTIPLE_FACES_FINAL_WARNING",
            message_ar=(
                f"ظهر أكثر من وجه واستمر في الكادر لأكثر من "
                f"{int(DEFAULT_CONFIG.multiple_faces_duration_s)} ثوانٍ. أخرج الوجه الآخر من الكادر الآن."
            ),
        )

    def _handle_phone_detected_opened(self, timestamp: float) -> None:
        """Count a shared warning and tell the student to put the phone down."""
        self._record_proctoring_warning(
            timestamp=timestamp,
            code="PHONE_DETECTED_WARNING",
            critical_code="PHONE_DETECTED_FINAL_WARNING",
            message_ar="تم رصد هاتف محمول. ضعه على الطاولة بعيداً عن يدك الآن.",
            audio_cue="phone_alarm",
        )

    def _update_multiple_faces_policy(
        self, signals: Mapping[str, object], timestamp: float
    ) -> None:
        """Track the start of a continuous multi-face run for the five-second timer."""
        face_count = int(signals.get("face_count", 0))  # type: ignore[arg-type]
        if face_count >= 2:
            if self._multiple_faces_start_ts is None:
                self._multiple_faces_start_ts = timestamp
                self._multiple_faces_warned = False
                self._multiple_faces_deadline_exceeded = False
        else:
            self._multiple_faces_start_ts = None
            self._multiple_faces_warned = False
            self._multiple_faces_deadline_exceeded = False

    def _close(self, event_type: str) -> Optional[EventRecord]:
        run = self._runs.pop(event_type, None)
        if run is None or not run.opened:
            return None
        event: EventRecord = {
            "type": event_type,
            "status": "closed",
            "start_time": run.start_time,
            "end_time": run.last_match,
            "duration": max(0.0, run.last_match - run.start_time),
            "confidence": run.calculate_confidence(),
            "snapshot_path": run.snapshot_path,
            "config_version": self.config_version,
        }
        self.events.append(event)
        return event

    def _has_frame_gap(self, timestamp: float) -> bool:
        return self._last_ts is not None and (timestamp - self._last_ts) > self.max_frame_gap_s

    def _handle_frame_gap(self, timestamp: float) -> list[EventRecord]:
        assert self._last_ts is not None
        emitted: list[EventRecord] = []
        for event_type in list(self._runs):
            closed = self._close(event_type)
            if closed:
                emitted.append(closed)
        self._multiple_faces_start_ts = None
        self._multiple_faces_warned = False
        self._multiple_faces_deadline_exceeded = False
        self.gaps.append((self._last_ts, timestamp))
        return emitted

    def _process_signal_for_rule(
        self,
        event_type: str,
        rule: Rule,
        matched: bool,
        timestamp: float,
        snapshot_path: Optional[str],
        signals: Mapping[str, object],
    ) -> Optional[EventRecord]:
        if matched:
            return self._record_match(event_type, rule, timestamp, snapshot_path, signals)
        return self._record_miss(event_type, rule)

    def _record_match(
        self,
        event_type: str,
        rule: Rule,
        timestamp: float,
        snapshot_path: Optional[str],
        signals: Mapping[str, object],
    ) -> Optional[EventRecord]:
        run = self._runs.get(event_type)
        if run is None:
            run = _EventRun(
                start_time=timestamp,
                last_match=timestamp,
                snapshot_path=snapshot_path,
            )
            self._runs[event_type] = run

        run.record_match(timestamp, snapshot_path)

        if run.meets_open_criteria(rule, timestamp):
            run.opened = True
            if event_type == "looking_away":
                self._handle_looking_away_opened(timestamp, signals)
            elif event_type == "multiple_faces":
                self._handle_multiple_faces_opened(timestamp)
            elif event_type == "phone_detected":
                self._handle_phone_detected_opened(timestamp)
            return {
                "type": event_type,
                "status": "opened",
                "start_time": run.start_time,
                "end_time": None,
                "duration": timestamp - run.start_time,
                "confidence": run.calculate_confidence(),
                "snapshot_path": run.snapshot_path,
                "config_version": self.config_version,
            }
        return None

    def _record_miss(self, event_type: str, rule: Rule) -> Optional[EventRecord]:
        run = self._runs.get(event_type)
        if run is None:
            return None

        run.record_miss()
        if run.misses > rule.tolerance_samples:
            return self._close(event_type)
        return None

    def update(
        self,
        signals: Mapping[str, object],
        timestamp: float,
        snapshot_path: Optional[str] = None,
    ) -> list[EventRecord]:
        """Update detection runs with new per-frame signals at given timestamp."""
        if self._last_ts is not None and timestamp <= self._last_ts:
            return []

        emitted: list[EventRecord] = []
        if self._has_frame_gap(timestamp):
            emitted.extend(self._handle_frame_gap(timestamp))

        self._update_multiple_faces_policy(signals, timestamp)

        for event_type, base_rule in self.rules.items():
            effective_rule = self._effective_rule_for_signals(
                event_type, base_rule, signals
            )
            matched = bool(effective_rule.predicate(signals))
            event = self._process_signal_for_rule(
                event_type=event_type,
                rule=effective_rule,
                matched=matched,
                timestamp=timestamp,
                snapshot_path=snapshot_path,
                signals=signals,
            )
            if event is not None:
                emitted.append(event)

        self._last_ts = timestamp
        return emitted

    def get_proctoring_status(self, current_time: Optional[float] = None) -> dict[str, Any]:
        """Return a snapshot of current warnings, remaining attempts, and multiple-face timer."""
        now = current_time if current_time is not None else (self._last_ts or 0.0)
        mf_remaining: Optional[float] = None
        if self._multiple_faces_start_ts is not None and not self._multiple_faces_warned:
            elapsed = max(0.0, now - self._multiple_faces_start_ts)
            mf_remaining = max(0.0, DEFAULT_CONFIG.multiple_faces_duration_s - elapsed)

        phone_remaining: Optional[float] = None
        phone_run = self._runs.get("phone_detected")
        if phone_run is not None and not phone_run.opened:
            elapsed = max(0.0, now - phone_run.start_time)
            phone_remaining = max(
                0.0, DEFAULT_CONFIG.phone_detected_duration_s - elapsed
            )

        return {
            "looking_away_attempts": self.looking_away_attempts,
            "warning_count": self.warning_count,
            "total_warning_count": self.warning_count,
            "max_warning_count": self.looking_away_critical_warning_attempt,
            "remaining_looking_away_warnings": max(
                0, self.looking_away_max_warnings - self.looking_away_attempts
            ),
            "max_regular_warnings": self.looking_away_max_warnings,
            "critical_warning_on_attempt": self.looking_away_critical_warning_attempt,
            # Kept as compatibility aliases for callers of the earlier status shape.
            "max_warnings_before_termination": self.looking_away_max_warnings,
            "terminate_on_attempt": self.looking_away_critical_warning_attempt,
            "exam_terminated": self.exam_terminated,
            "termination_reason": self.termination_reason,
            "multiple_faces_countdown_remaining_s": mf_remaining,
            "phone_detected_countdown_remaining_s": phone_remaining,
            "allows_extended_looking_down": False,
            "effective_looking_down_limit_s": self.looking_away_grace_s,
            "exam_context": self.exam_context.to_dict(),
            "latest_notification": self.notifications[-1] if self.notifications else None,
        }

    def flush(self) -> list[EventRecord]:
        """Close all pending open runs and return emitted closed event records."""
        emitted: list[EventRecord] = []
        for event_type in list(self._runs):
            closed = self._close(event_type)
            if closed is not None:
                emitted.append(closed)
        return emitted
