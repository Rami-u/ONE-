"""Evaluate event detection against labeled video intervals."""

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Optional
import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.vision.pipeline import EventBuilder, analyze_frame
from backend.vision.event_builder import EventRecord

EVAL_DIR = Path(__file__).resolve().parent
CLIPS_DIR = EVAL_DIR / "clips"
LABELS_CSV = EVAL_DIR / "labels.csv"
REPORTS_DIR = EVAL_DIR / "reports"
GATES_PATH = EVAL_DIR / "gates.yaml"

SECONDS_PER_HOUR: float = 3600.0
DEFAULT_SAMPLING_INTERVAL_S: float = 1.0

EVAL_EVENT_TYPES: tuple[str, ...] = (
    "face_missing",
    "multiple_faces",
    "looking_away",
    "phone_detected",
)
SUPPORTED_GROUP_COLUMNS: tuple[str, ...] = (
    "lighting",
    "glasses",
    "headscarf",
    "camera_angle",
    "skin_tone_bucket",
    "device",
)


@dataclass
class GroundTruthInterval:
    event_type: str
    start_sec: float
    end_sec: float
    groups: dict[str, str] = field(default_factory=dict)
    matched: bool = False


def load_ground_truth(
    csv_path: Path,
) -> tuple[dict[str, list[GroundTruthInterval]], dict[str, dict[str, str]], list[str]]:
    """Read labels plus optional clip-level demographic/device group columns."""
    gt_by_video: dict[str, list[GroundTruthInterval]] = defaultdict(list)
    groups_by_video: dict[str, dict[str, str]] = defaultdict(dict)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Labels file not found at: {csv_path}")

    with csv_path.open(mode="r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        group_columns = [col for col in SUPPORTED_GROUP_COLUMNS if col in headers]
        for row in reader:
            video = (row.get("video") or "").strip()
            if not video:
                continue
            group_values = {
                col: (row.get(col) or "").strip()
                for col in group_columns
                if (row.get(col) or "").strip()
            }
            for col, value in group_values.items():
                groups_by_video[video].setdefault(col, value)

            event_type = (row.get("event_type") or "").strip()
            if not event_type or event_type.lower() == "none":
                continue

            gt_by_video[video].append(
                GroundTruthInterval(
                    event_type=event_type,
                    start_sec=float(row["start_sec"]),
                    end_sec=float(row["end_sec"]),
                    groups=group_values,
                )
            )

    return dict(gt_by_video), dict(groups_by_video), group_columns


def intervals_overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> bool:
    """Return whether two closed intervals overlap."""
    return max(start_a, start_b) <= min(end_a, end_b)


def run_pipeline_on_video(
    video_path: Path, sample_every_sec: float = DEFAULT_SAMPLING_INTERVAL_S
) -> Optional[list[EventRecord]]:
    """Simulate browser frame sampling and return closed lifecycle records."""
    if video_path.stat().st_size == 0:
        print(f"[WARN] Skipping empty (0-byte) file: {video_path.name}")
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[WARN] Skipping unreadable or corrupted video file: {video_path.name}")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(int(round(fps * sample_every_sec)), 1)
    builder = EventBuilder()
    frame_idx = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % step == 0:
                timestamp = frame_idx / fps
                ok_enc, encoded_buf = cv2.imencode(".jpg", frame)
                if ok_enc:
                    signals = analyze_frame(encoded_buf.tobytes(), timestamp)
                    builder.update(signals, timestamp)
            frame_idx += 1
    finally:
        cap.release()

    builder.flush()
    return builder.events


def video_duration_seconds(path: Path) -> float:
    """Compute duration of a video file in seconds."""
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        return frames / fps if fps and frames else 0.0
    finally:
        cap.release()


def empty_counts() -> dict[str, dict[str, int]]:
    """Generate zeroed TP/FP/FN tally dictionaries for all event types."""
    return {event_type: {"TP": 0, "FP": 0, "FN": 0} for event_type in EVAL_EVENT_TYPES}


def metrics_from_counts(
    counts: dict[str, dict[str, int]], evaluated_hours: float
) -> dict[str, dict[str, float | int]]:
    """Calculate precision, recall, and false alarm rate from confusion tallies."""
    metrics = {}
    for event_type in EVAL_EVENT_TYPES:
        row = counts[event_type]
        tp, fp, fn = row["TP"], row["FP"], row["FN"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        false_alarms = fp / evaluated_hours if evaluated_hours > 0 else 0.0
        metrics[event_type] = {
            **row,
            "precision": precision,
            "recall": recall,
            "false_alarms_per_student_hour": false_alarms,
        }
    return metrics


def read_gates(path: Path = GATES_PATH) -> dict[str, dict[str, Optional[float]]]:
    """Parse the minimal gates.yaml file format without an external YAML dependency."""
    gates: dict[str, dict[str, Optional[float]]] = {}
    current_section: Optional[str] = None
    if not path.is_file():
        raise FileNotFoundError(f"Gate file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            current_section = line.strip().removesuffix(":")
            gates[current_section] = {}
            continue
        if current_section is None or ":" not in line:
            raise ValueError(f"Invalid gate config line: {raw_line}")
        key, raw_value = (part.strip() for part in line.split(":", 1))
        gates[current_section][key] = (
            None if raw_value == "TODO_SET_BY_HUMAN" else float(raw_value)
        )
    return gates


def check_gates(
    report: dict[str, Any], gates: dict[str, dict[str, Optional[float]]]
) -> tuple[bool, list[str]]:
    """Verify evaluation metrics against defined quality gate thresholds."""
    failures: list[str] = []
    metrics = report["metrics"]

    for event_type in EVAL_EVENT_TYPES:
        event_gates = gates.get(event_type)
        if not event_gates:
            failures.append(f"{event_type}: gate is missing")
            continue

        required_keys = ("min_recall", "max_false_alarms_per_student_hour")
        for key in required_keys:
            if key not in event_gates or event_gates[key] is None:
                failures.append(f"{event_type}: {key} is unset (TODO_SET_BY_HUMAN)")

        if any(event_gates.get(key) is None for key in required_keys):
            continue

        actual = metrics[event_type]
        min_recall = event_gates["min_recall"]
        max_fa = event_gates["max_false_alarms_per_student_hour"]

        if actual["recall"] < min_recall:
            failures.append(
                f"{event_type}: recall {actual['recall']:.4f} below {min_recall:.4f}"
            )
        if actual["false_alarms_per_student_hour"] > max_fa:
            failures.append(
                f"{event_type}: false alarms/hour "
                f"{actual['false_alarms_per_student_hour']:.4f} above {max_fa:.4f}"
            )

    return not failures, failures


def evaluate_dataset(
    clips_dir: Path = CLIPS_DIR,
    labels_csv: Path = LABELS_CSV,
    interval: float = DEFAULT_SAMPLING_INTERVAL_S,
    write_report: bool = True,
    print_summary: bool = True,
) -> dict[str, Any]:
    """Run full evaluation suite over test clips and compute benchmark metrics."""
    if interval <= 0:
        raise ValueError("interval must be positive")

    gt_by_video, groups_by_video, group_columns = load_ground_truth(labels_csv)
    overall_counts = empty_counts()
    clip_reports: dict[str, Any] = {}
    group_counts: dict[str, dict[str, dict[str, dict[str, int]]]] = {
        col: defaultdict(empty_counts) for col in group_columns
    }
    group_duration_s: dict[str, dict[str, float]] = {
        col: defaultdict(float) for col in group_columns
    }

    all_video_names = sorted(
        ({p.name for p in clips_dir.glob("*.mp4")} if clips_dir.is_dir() else set())
        | set(gt_by_video)
    )
    processed_videos = 0
    total_duration_s = 0.0
    skipped_labeled_videos: list[str] = []

    for video_name in all_video_names:
        video_path = clips_dir / video_name
        if not video_path.is_file():
            print(f"[SKIP] Video file not found on disk: {video_name}")
            if video_name in gt_by_video:
                skipped_labeled_videos.append(video_name)
            continue

        predictions = run_pipeline_on_video(video_path, sample_every_sec=interval)
        if predictions is None:
            continue

        processed_videos += 1
        duration_s = video_duration_seconds(video_path)
        total_duration_s += duration_s

        for col in group_columns:
            val = groups_by_video.get(video_name, {}).get(col, "unknown")
            group_duration_s[col][val] += duration_s

        gt_intervals = gt_by_video.get(video_name, [])
        clip_counts = empty_counts()

        for pred in predictions:
            event_type = pred["type"]
            if event_type not in overall_counts:
                continue

            pred_start = float(pred["start_time"])
            pred_end = float(
                pred["end_time"]
                if pred.get("end_time") is not None
                else pred_start + float(pred["duration"])
            )
            matched_gt = next(
                (
                    gt
                    for gt in gt_intervals
                    if not gt.matched
                    and gt.event_type == event_type
                    and intervals_overlap(pred_start, pred_end, gt.start_sec, gt.end_sec)
                ),
                None,
            )
            metric_key = "TP" if matched_gt else "FP"
            overall_counts[event_type][metric_key] += 1
            clip_counts[event_type][metric_key] += 1

            if matched_gt:
                matched_gt.matched = True

            for col in group_columns:
                val = groups_by_video.get(video_name, {}).get(col, "unknown")
                group_counts[col][val][event_type][metric_key] += 1

        for gt in gt_intervals:
            if gt.event_type in overall_counts and not gt.matched:
                overall_counts[gt.event_type]["FN"] += 1
                clip_counts[gt.event_type]["FN"] += 1
                for col in group_columns:
                    val = gt.groups.get(
                        col, groups_by_video.get(video_name, {}).get(col, "unknown")
                    )
                    group_counts[col][val][gt.event_type]["FN"] += 1

        clip_reports[video_name] = {
            "duration_seconds": duration_s,
            "counts": clip_counts,
        }

    total_hours = total_duration_s / SECONDS_PER_HOUR
    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sampling_interval_seconds": interval,
        "processed_videos": processed_videos,
        "evaluated_video_seconds": total_duration_s,
        "evaluated_video_hours": total_hours,
        "skipped_labeled_videos": skipped_labeled_videos,
        "metrics": metrics_from_counts(overall_counts, total_hours),
        "ground_truth_events": {
            event_type: overall_counts[event_type]["TP"] + overall_counts[event_type]["FN"]
            for event_type in EVAL_EVENT_TYPES
        },
        "per_clip": clip_reports,
        "group_columns": group_columns,
        "per_group": {
            col: {
                val: metrics_from_counts(
                    counts, group_duration_s[col][val] / SECONDS_PER_HOUR
                )
                for val, counts in values.items()
            }
            for col, values in group_counts.items()
        },
    }

    if print_summary:
        _print_summary(processed_videos, len(all_video_names), total_hours, report)

    if write_report:
        _save_reports(report)

    return report


def _print_summary(
    processed_videos: int, total_videos: int, total_hours: float, report: dict[str, Any]
) -> None:
    """Print readable table summary of evaluation results to stdout."""
    print(f"\nProcessed valid videos: {processed_videos}/{total_videos}")
    print(f"Evaluated video hours: {total_hours:.6f}")
    header = (
        f"{'Event Type':<18} | {'TP':<4} | {'FP':<4} | {'FN':<4} | "
        f"{'Precision':<10} | {'Recall':<10} | {'False alarms/h':<15}"
    )
    print(header)
    print("-" * len(header))
    for event_type, row in report["metrics"].items():
        print(
            f"{event_type:<18} | {row['TP']:<4} | {row['FP']:<4} | {row['FN']:<4} | "
            f"{row['precision']:<10.2%} | {row['recall']:<10.2%} | "
            f"{row['false_alarms_per_student_hour']:<15.3f}"
        )
    for col, values in report["per_group"].items():
        print(f"\nGroup breakdown: {col}")
        for val, metrics in values.items():
            breakdown = ", ".join(
                f"{kind} recall={row['recall']:.2%}, FA/h={row['false_alarms_per_student_hour']:.3f}"
                for kind, row in metrics.items()
            )
            print(f"  {val}: {breakdown}")


def _save_reports(report: dict[str, Any]) -> None:
    """Write evaluation report to timestamped JSON and Markdown files."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = REPORTS_DIR / f"{stamp}.json"
    md_path = REPORTS_DIR / f"{stamp}.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote reports: {json_path} and {md_path}")
    report["report_json_path"] = str(json_path)
    report["report_markdown_path"] = str(md_path)


def render_markdown(report: dict[str, Any]) -> str:
    """Render markdown summary of evaluation metrics and per-clip breakdown."""
    lines = [
        "# Evaluation report",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Sampling interval: {report['sampling_interval_seconds']} s",
        f"- Processed videos: {report['processed_videos']}",
        f"- Labeled videos skipped (missing files): {', '.join(report.get('skipped_labeled_videos', [])) or 'none'}",
        f"- Evaluated video hours: {report['evaluated_video_hours']:.6f}",
        "",
        "| Event type | TP | FP | FN | Precision | Recall | False alarms / student-hour |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for event_type, row in report["metrics"].items():
        lines.append(
            f"| {event_type} | {row['TP']} | {row['FP']} | {row['FN']} | "
            f"{row['precision']:.2%} | {row['recall']:.2%} | "
            f"{row['false_alarms_per_student_hour']:.3f} |"
        )
    lines += [
        "",
        "## Per-clip counts",
        "",
        "| Clip | Duration (s) | Event type | TP | FP | FN |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for clip, detail in report["per_clip"].items():
        for event_type, counts in detail["counts"].items():
            lines.append(
                f"| {clip} | {detail['duration_seconds']:.3f} | {event_type} | "
                f"{counts['TP']} | {counts['FP']} | {counts['FN']} |"
            )
    for col, values in report["per_group"].items():
        lines += [
            "",
            f"## Group: {col}",
            "",
            "| Value | Event type | TP | FP | FN | Precision | Recall | False alarms / student-hour |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for val, metrics in values.items():
            for event_type, row in metrics.items():
                lines.append(
                    f"| {val} | {event_type} | {row['TP']} | {row['FP']} | {row['FN']} | "
                    f"{row['precision']:.2%} | {row['recall']:.2%} | "
                    f"{row['false_alarms_per_student_hour']:.3f} |"
                )
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_SAMPLING_INTERVAL_S,
        help="frame sampling interval in seconds (default: 1.0)",
    )
    parser.add_argument("--check-gates", action="store_true")
    parser.add_argument("--no-report", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json-stdout", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.interval <= 0:
        parser.error("--interval must be positive")

    report = evaluate_dataset(
        interval=args.interval,
        write_report=not args.no_report,
        print_summary=not args.json_stdout,
    )
    gate_status = 0
    if args.check_gates:
        passed, failures = check_gates(report, read_gates())
        if passed:
            print("All evaluation gates passed.")
        else:
            print("Evaluation gates failed:")
            for failure in failures:
                print(f"- {failure}")
            gate_status = 1

    if args.json_stdout:
        print("METRICS_JSON=" + json.dumps(report, separators=(",", ":")))
    return gate_status


if __name__ == "__main__":
    raise SystemExit(main())
