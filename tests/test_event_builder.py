from backend.vision.event_builder import EventBuilder, Rule


def create_frame_signals(face_missing: bool = False) -> dict[str, object]:
    """Helper to generate mock frame signals for testing."""
    return {
        "face_count": 0 if face_missing else 1,
        "looking_away": False,
        "phone_detected": False,
    }


def test_flicker_opens_when_enough_samples_match():
    builder = EventBuilder()
    outputs = []
    missing_pattern = [1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1]
    for timestamp, is_missing in enumerate(missing_pattern):
        signals = create_frame_signals(face_missing=bool(is_missing))
        outputs.extend(builder.update(signals, float(timestamp)))

    assert any(
        event["type"] == "face_missing" and event["status"] == "opened"
        for event in outputs
    )


def test_large_gap_closes_at_last_evidence_and_records_gap():
    builder = EventBuilder()
    for timestamp in (0.0, 1.0, 2.0, 3.0):
        builder.update(create_frame_signals(face_missing=True), timestamp)

    emitted_after_gap = builder.update(create_frame_signals(face_missing=True), 60.0)
    closed_events = [
        event
        for event in emitted_after_gap
        if event["type"] == "face_missing" and event["status"] == "closed"
    ]
    assert len(closed_events) == 1
    assert closed_events[0]["end_time"] == 3.0
    assert closed_events[0]["duration"] == 3.0
    assert builder.gaps == [(3.0, 60.0)]


def test_flush_closes_with_final_duration():
    builder = EventBuilder()
    for timestamp in range(11):
        builder.update(create_frame_signals(face_missing=True), float(timestamp))

    assert builder.events == []
    builder.update(create_frame_signals(face_missing=False), 11.0)
    builder.flush()
    assert builder.events[-1]["duration"] == 10.0
    assert builder.events[-1]["status"] == "closed"


def test_event_confidence_is_fraction_of_matching_samples():
    custom_rule = {"missing": Rule(min_duration_s=1.0, predicate=lambda s: s["face_count"] == 0)}
    builder = EventBuilder(rules=custom_rule)
    for timestamp, is_missing in enumerate([True, True, False, True]):
        builder.update(create_frame_signals(face_missing=is_missing), float(timestamp))

    builder.update(create_frame_signals(face_missing=False), 4.0)
    builder.update(create_frame_signals(face_missing=False), 5.0)
    assert builder.events[0]["confidence"] == 0.5


def test_out_of_order_timestamp_is_ignored():
    builder = EventBuilder()
    builder.update(create_frame_signals(face_missing=True), 2.0)
    assert builder.update(create_frame_signals(face_missing=False), 1.0) == []
    assert builder._last_ts == 2.0


def test_unopened_run_is_discarded():
    custom_rule = {"missing": Rule(min_duration_s=5.0, predicate=lambda s: s["face_count"] == 0)}
    builder = EventBuilder(rules=custom_rule)
    builder.update(create_frame_signals(face_missing=True), 0.0)
    builder.update(create_frame_signals(face_missing=False), 1.0)
    builder.update(create_frame_signals(face_missing=False), 2.0)
    assert builder.events == []


def test_opened_and_closed_are_lifecycle_records():
    custom_rule = {"missing": Rule(min_duration_s=1.0, predicate=lambda s: s["face_count"] == 0)}
    builder = EventBuilder(rules=custom_rule)
    builder.update(create_frame_signals(face_missing=True), 0.0)
    opened_events = builder.update(create_frame_signals(face_missing=True), 1.0)
    assert opened_events[0]["status"] == "opened"

    builder.update(create_frame_signals(face_missing=False), 2.0)
    closed_events = builder.update(create_frame_signals(face_missing=False), 3.0)
    assert closed_events[0]["status"] == "closed"
    assert set(closed_events[0]) == {
        "type",
        "status",
        "start_time",
        "end_time",
        "duration",
        "confidence",
        "snapshot_path",
        "config_version",
    }


def test_single_missed_sample_is_tolerated():
    custom_rule = {"missing": Rule(min_duration_s=2.0, predicate=lambda s: s["face_count"] == 0)}
    builder = EventBuilder(rules=custom_rule)
    outputs = []
    for timestamp, is_missing in enumerate([True, True, False, True, True]):
        outputs.extend(builder.update(create_frame_signals(face_missing=is_missing), float(timestamp)))

    assert any(event["status"] == "opened" for event in outputs)


def test_tolerance_exceeded_closes_at_last_matching_sample():
    custom_rule = {"missing": Rule(min_duration_s=1.0, predicate=lambda s: s["face_count"] == 0)}
    builder = EventBuilder(rules=custom_rule)
    builder.update(create_frame_signals(face_missing=True), 0.0)
    builder.update(create_frame_signals(face_missing=True), 1.0)
    builder.update(create_frame_signals(face_missing=False), 2.0)
    closed_events = builder.update(create_frame_signals(face_missing=False), 3.0)
    assert closed_events[0]["end_time"] == 1.0


def test_tolerated_miss_reduces_confidence():
    custom_rule = {"missing": Rule(min_duration_s=2.0, predicate=lambda s: s["face_count"] == 0)}
    builder = EventBuilder(rules=custom_rule)
    for timestamp, is_missing in enumerate([True, True, False, True, True]):
        builder.update(create_frame_signals(face_missing=is_missing), float(timestamp))

    builder.update(create_frame_signals(face_missing=False), 5.0)
    builder.update(create_frame_signals(face_missing=False), 6.0)
    assert builder.events[0]["confidence"] == 4 / 7


def test_gap_closes_short_unopened_run_without_phantom_event():
    custom_rule = {"missing": Rule(min_duration_s=10.0, predicate=lambda s: s["face_count"] == 0)}
    builder = EventBuilder(rules=custom_rule)
    builder.update(create_frame_signals(face_missing=True), 0.0)
    assert builder.update(create_frame_signals(face_missing=True), 60.0) == []
    assert builder.events == []
    assert builder.gaps == [(0.0, 60.0)]


def test_from_state_reads_legacy_looking_away_attempt_setting():
    builder = EventBuilder.from_state({"looking_away_terminate_attempt": 4})

    assert builder.looking_away_critical_warning_attempt == 4
