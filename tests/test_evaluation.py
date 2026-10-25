import csv
from pathlib import Path
import pytest

from evaluation.evaluate import (
    EVAL_EVENT_TYPES,
    check_gates,
    empty_counts,
    load_ground_truth,
    metrics_from_counts,
)


def test_metrics_counts_and_student_hours():
    counts = empty_counts()
    counts["face_missing"].update(TP=2, FP=1, FN=1)
    metric_row = metrics_from_counts(counts, evaluated_hours=0.5)["face_missing"]

    assert (metric_row["TP"], metric_row["FP"], metric_row["FN"]) == (2, 1, 1)
    assert metric_row["precision"] == pytest.approx(2.0 / 3.0)
    assert metric_row["recall"] == pytest.approx(2.0 / 3.0)
    assert metric_row["false_alarms_per_student_hour"] == 2.0


def test_unset_gate_fails_and_configured_gate_passes():
    counts = empty_counts()
    report = {"metrics": metrics_from_counts(counts, evaluated_hours=1.0)}
    unset_gates = {
        event: {"min_recall": None, "max_false_alarms_per_student_hour": None}
        for event in EVAL_EVENT_TYPES
    }
    passed, failures = check_gates(report, unset_gates)
    assert not passed
    assert len(failures) == len(EVAL_EVENT_TYPES) * 2

    configured_gates = {
        event: {"min_recall": 0.0, "max_false_alarms_per_student_hour": 0.0}
        for event in EVAL_EVENT_TYPES
    }
    assert check_gates(report, configured_gates) == (True, [])


def test_group_columns_and_none_label_are_loaded(tmp_path: Path):
    labels_path = tmp_path / "labels.csv"
    with labels_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["video", "start_sec", "end_sec", "event_type", "lighting", "device"],
        )
        writer.writeheader()
        writer.writerow({
            "video": "sample.mp4",
            "start_sec": 0,
            "end_sec": 2,
            "event_type": "none",
            "lighting": "low",
            "device": "usb_cam",
        })
        writer.writerow({
            "video": "sample.mp4",
            "start_sec": 2,
            "end_sec": 4,
            "event_type": "face_missing",
            "lighting": "low",
            "device": "usb_cam",
        })

    ground_truth, groups, columns = load_ground_truth(labels_path)
    assert columns == ["lighting", "device"]
    assert groups["sample.mp4"] == {"lighting": "low", "device": "usb_cam"}
    assert len(ground_truth["sample.mp4"]) == 1
    assert ground_truth["sample.mp4"][0].event_type == "face_missing"
