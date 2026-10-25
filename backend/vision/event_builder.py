"""Time-filter per-frame vision signals into lifecycle event records."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Mapping, Optional, TypedDict

from .config import DEFAULT_CONFIG


class EventRecord(TypedDict):
    type: str
    status: str
    start_time: float
    end_time: Optional[float]
    duration: float
    confidence: float
    snapshot_path: Optional[str]
    config_version: str


@dataclass(frozen=True)
class Rule:
    min_duration_s: float
    predicate: Callable[[Mapping[str, object]], bool]
    tolerance_samples: int = 1
    min_samples: int = 2


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
        )


def default_rules() -> dict[str, Rule]:
    """Construct default detection rules initialized from current VisionConfig."""
    return {
        "face_missing": Rule(
            min_duration_s=DEFAULT_CONFIG.face_missing_duration_s,
            predicate=lambda s: s["face_count"] == 0,
            tolerance_samples=DEFAULT_CONFIG.tolerance_samples,
            min_samples=DEFAULT_CONFIG.min_samples,
        ),
        "multiple_faces": Rule(
            min_duration_s=DEFAULT_CONFIG.multiple_faces_duration_s,
            predicate=lambda s: s["face_count"] >= 2,
            tolerance_samples=DEFAULT_CONFIG.tolerance_samples,
            min_samples=DEFAULT_CONFIG.min_samples,
        ),
        "looking_away": Rule(
            min_duration_s=DEFAULT_CONFIG.looking_away_duration_s,
            predicate=lambda s: bool(s["looking_away"]),
            tolerance_samples=DEFAULT_CONFIG.tolerance_samples,
            min_samples=DEFAULT_CONFIG.min_samples,
        ),
        "phone_detected": Rule(
            min_duration_s=DEFAULT_CONFIG.phone_detected_duration_s,
            predicate=lambda s: bool(s["phone_detected"]),
            tolerance_samples=DEFAULT_CONFIG.tolerance_samples,
            min_samples=DEFAULT_CONFIG.min_samples,
        ),
    }


class EventBuilder:
    """Build events from signals, closing runs only at last observed evidence."""

    def __init__(
        self,
        rules: Optional[dict[str, Rule]] = None,
        max_frame_gap_s: float = DEFAULT_CONFIG.max_frame_gap_s,
        config_version: str = DEFAULT_CONFIG.config_version,
    ) -> None:
        self.rules = dict(rules or default_rules())
        self.max_frame_gap_s = max_frame_gap_s
        self.config_version = config_version
        self._runs: dict[str, _EventRun] = {}
        self._last_ts: Optional[float] = None
        self.gaps: list[tuple[float, float]] = []
        self.events: list[EventRecord] = []

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
        builder = cls(
            rules=rules,
            max_frame_gap_s=max_frame_gap_s,
            config_version=resolved_version,
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
        return builder

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
        self.gaps.append((self._last_ts, timestamp))
        return emitted

    def _process_signal_for_rule(
        self,
        event_type: str,
        rule: Rule,
        matched: bool,
        timestamp: float,
        snapshot_path: Optional[str],
    ) -> Optional[EventRecord]:
        if matched:
            return self._record_match(event_type, rule, timestamp, snapshot_path)
        return self._record_miss(event_type, rule)

    def _record_match(
        self,
        event_type: str,
        rule: Rule,
        timestamp: float,
        snapshot_path: Optional[str],
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

        for event_type, rule in self.rules.items():
            matched = bool(rule.predicate(signals))
            event = self._process_signal_for_rule(
                event_type=event_type,
                rule=rule,
                matched=matched,
                timestamp=timestamp,
                snapshot_path=snapshot_path,
            )
            if event is not None:
                emitted.append(event)

        self._last_ts = timestamp
        return emitted

    def flush(self) -> list[EventRecord]:
        """Close all pending open runs and return emitted closed event records."""
        emitted: list[EventRecord] = []
        for event_type in list(self._runs):
            closed = self._close(event_type)
            if closed is not None:
                emitted.append(closed)
        return emitted
