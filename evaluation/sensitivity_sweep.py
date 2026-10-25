"""Run evaluation over yaw/pitch threshold combinations without changing config."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CORE_EVENTS: tuple[str, ...] = ("face_missing", "multiple_faces", "looking_away")

DEFAULT_YAW_GRID: str = "25,30,35"
DEFAULT_PITCH_DOWN_GRID: str = "-20,-25,-30"
DEFAULT_SWEEP_INTERVAL_S: float = 1.0
METRICS_MARKER: str = "METRICS_JSON="
SUBPROCESS_TIMEOUT_SECONDS: int = 180


def parse_grid(raw: str) -> list[float]:
    """Parse comma-separated numerical grid string into a float list."""
    try:
        values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("grid must be comma-separated numbers") from exc
    if not values:
        raise argparse.ArgumentTypeError("grid must contain at least one number")
    return values


def run_sweep(
    yaw_values: list[float], pitch_values: list[float], interval: float
) -> list[dict[str, Any]]:
    """Execute evaluation matrix across yaw and pitch-down threshold permutations."""
    rows: list[dict[str, Any]] = []
    for yaw in yaw_values:
        for pitch in pitch_values:
            env = os.environ.copy()
            env["VISION_YAW_THRESHOLD"] = str(yaw)
            env["VISION_PITCH_DOWN_THRESHOLD"] = str(pitch)
            command = [
                sys.executable,
                "-m",
                "evaluation.evaluate",
                "--no-report",
                "--json-stdout",
                "--interval",
                str(interval),
            ]
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT_SECONDS,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"Evaluation failed for yaw={yaw}, pitch_down={pitch} "
                    f"(exit {completed.returncode}):\n{completed.stderr}\n{completed.stdout}"
                )

            marker = next(
                (
                    line[len(METRICS_MARKER):]
                    for line in completed.stdout.splitlines()
                    if line.startswith(METRICS_MARKER)
                ),
                None,
            )
            if marker is None:
                raise RuntimeError(
                    f"Evaluation output missing metrics for yaw={yaw}, pitch_down={pitch}"
                )

            report = json.loads(marker)
            supported = [
                event
                for event in CORE_EVENTS
                if report["ground_truth_events"][event] > 0
            ]
            macro_recall = (
                sum(report["metrics"][event]["recall"] for event in supported)
                / len(supported)
                if supported
                else None
            )
            fa_per_hour = sum(
                report["metrics"][event]["false_alarms_per_student_hour"]
                for event in CORE_EVENTS
            )
            rows.append(
                {
                    "yaw_threshold": yaw,
                    "pitch_down_threshold": pitch,
                    "macro_recall": macro_recall,
                    "core_false_alarms_per_student_hour": fa_per_hour,
                    "processed_videos": report["processed_videos"],
                    "evaluated_video_hours": report["evaluated_video_hours"],
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yaw", type=parse_grid, default=parse_grid(DEFAULT_YAW_GRID)
    )
    parser.add_argument(
        "--pitch-down",
        type=parse_grid,
        default=parse_grid(DEFAULT_PITCH_DOWN_GRID),
    )
    parser.add_argument(
        "--interval", type=float, default=DEFAULT_SWEEP_INTERVAL_S
    )
    args = parser.parse_args(argv)

    if args.interval <= 0:
        parser.error("--interval must be positive")

    rows = run_sweep(args.yaw, args.pitch_down, args.interval)
    print("Threshold sensitivity (trade-off only; no threshold is applied)")
    print(
        f"{'Yaw':>7} {'Pitch down':>12} {'Macro recall':>14} "
        f"{'Core FA/hour':>14} {'Videos':>8} {'Hours':>10}"
    )
    for row in rows:
        recall_text = (
            f"{row['macro_recall']:.3f}" if row["macro_recall"] is not None else "N/A"
        )
        print(
            f"{row['yaw_threshold']:>7.1f} {row['pitch_down_threshold']:>12.1f} "
            f"{recall_text:>14} "
            f"{row['core_false_alarms_per_student_hour']:>14.3f} "
            f"{row['processed_videos']:>8} {row['evaluated_video_hours']:>10.6f}"
        )
    print(
        "Reminder: interpret only with representative labeled clips; "
        "this script never edits config files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
