"""Replay real clip frames through FrameWorker at simulated student intervals."""

import argparse
from concurrent.futures import Future
from datetime import date
from pathlib import Path
import re
import sys
import time
import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.vision.worker import BackpressureError, FrameWorker, StaleFrameError

DEFAULT_STUDENTS_COUNT: int = 1
DEFAULT_FRAME_INTERVAL_SECONDS: float = 2.0
DEFAULT_TEST_DURATION_SECONDS: float = 120.0
DEFAULT_WORKERS_COUNT: int = 4
DEFAULT_QUEUE_SIZE: int = 16
DEFAULT_MAX_FRAME_AGE_SECONDS: float = 4.0

MAX_ALLOWED_P95_LATENCY_MS: float = 2000.0
CAPACITY_HEADROOM_MULTIPLIER: float = 2.0
MILLISECONDS_PER_SECOND: float = 1000.0


def read_jpegs(path: Path) -> list[bytes]:
    """Extract and JPEG-encode all readable frames from video path."""
    cap = cv2.VideoCapture(str(path))
    frames: list[bytes] = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            ok_enc, encoded = cv2.imencode(".jpg", frame)
            if ok_enc:
                frames.append(encoded.tobytes())
    finally:
        cap.release()
    if not frames:
        raise RuntimeError(f"No readable frames in {path}")
    return frames


def _compute_percentile(sorted_values: list[float], percentile_ratio: float) -> float:
    """Calculate percentile value from a pre-sorted list of numbers."""
    if not sorted_values:
        return 0.0
    index = min(
        len(sorted_values) - 1,
        max(0, int(round((len(sorted_values) - 1) * percentile_ratio))),
    )
    return sorted_values[index]


def run_load(
    worker: FrameWorker,
    frames: list[bytes],
    students: int,
    interval: float,
    duration: float,
) -> dict[str, float | int]:
    """Execute simulated concurrent student submissions against the FrameWorker."""
    started = time.monotonic()
    end_at = started + duration
    next_frame_time = [started] * students
    submitted = completed = dropped = 0
    latencies: list[float] = []
    pending: dict[Future, float] = {}
    sequence = 0

    while time.monotonic() < end_at or pending:
        now = time.monotonic()
        if now < end_at:
            for student_id in range(students):
                if next_frame_time[student_id] <= now:
                    payload = frames[sequence % len(frames)]
                    future = worker.submit(student_id, payload, time.time())
                    submitted += 1
                    pending[future] = time.perf_counter()
                    next_frame_time[student_id] += interval
                    sequence += 1

        for future, sent_at in list(pending.items()):
            if future.done():
                pending.pop(future)
                try:
                    future.result()
                    completed += 1
                    latencies.append(
                        (time.perf_counter() - sent_at) * MILLISECONDS_PER_SECOND
                    )
                except (BackpressureError, StaleFrameError):
                    dropped += 1
                except Exception:
                    dropped += 1

        if pending:
            time.sleep(0.002)

    ordered = sorted(latencies)
    return {
        "students": students,
        "submitted": submitted,
        "completed": completed,
        "dropped": dropped,
        "drop_rate": dropped / submitted if submitted else 0.0,
        "p50_ms": _compute_percentile(ordered, 0.50),
        "p95_ms": _compute_percentile(ordered, 0.95),
        "p99_ms": _compute_percentile(ordered, 0.99),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students", type=int, default=DEFAULT_STUDENTS_COUNT)
    parser.add_argument(
        "--sweep-students",
        default="",
        help="comma-separated N values for capacity sweep",
    )
    parser.add_argument(
        "--interval", type=float, default=DEFAULT_FRAME_INTERVAL_SECONDS
    )
    parser.add_argument(
        "--duration", type=float, default=DEFAULT_TEST_DURATION_SECONDS
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS_COUNT)
    parser.add_argument("--queue-size", type=int, default=DEFAULT_QUEUE_SIZE)
    parser.add_argument(
        "--max-frame-age", type=float, default=DEFAULT_MAX_FRAME_AGE_SECONDS
    )
    parser.add_argument(
        "--clip",
        type=Path,
        default=ROOT / "evaluation" / "clips" / "clip_01_normal.mp4",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.students < 1 or args.interval <= 0 or args.duration <= 0:
        parser.error("students, interval and duration must be positive")

    frames = read_jpegs(args.clip)
    levels = (
        [int(value) for value in args.sweep_students.split(",") if value.strip()]
        if args.sweep_students
        else [args.students]
    )
    if any(value < 1 for value in levels):
        parser.error("all student counts must be positive")

    reports: list[dict[str, float | int]] = []
    with FrameWorker(
        frames[0],
        max_workers=args.workers,
        queue_size=args.queue_size,
        max_frame_age_s=args.max_frame_age,
    ) as worker:
        for students in levels:
            reports.append(
                run_load(worker, frames, students, args.interval, args.duration)
            )
        stale_drops = worker.frames_dropped_stale

    print(
        "| Students | Submitted | Completed | Dropped | Drop rate | p50 ms | p95 ms | p99 ms |"
    )
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in reports:
        print(
            f"| {result['students']} | {result['submitted']} | {result['completed']} | "
            f"{result['dropped']} | {result['drop_rate']:.2%} | {result['p50_ms']:.2f} | "
            f"{result['p95_ms']:.2f} | {result['p99_ms']:.2f} |"
        )
    print(f"frames_dropped_stale={stale_drops}")

    eligible = [
        int(r["students"])
        for r in reports
        if float(r["p95_ms"]) < MAX_ALLOWED_P95_LATENCY_MS and float(r["drop_rate"]) == 0.0
    ]
    max_supported = max(eligible) if eligible else 0

    concurrency_report = (
        ROOT / "docs" / "benchmarks" / f"concurrency_{date.today().isoformat()}.md"
    )
    if not concurrency_report.is_file():
        raise RuntimeError(
            "Run python -m evaluation.bench_concurrency before load_test to supply measured_ms"
        )

    concurrency_text = concurrency_report.read_text(encoding="utf-8")
    process_row = re.search(r"\| 4 processes \| ([0-9.]+) \|", concurrency_text)
    if not process_row:
        raise RuntimeError(
            f"Could not read measured 4-process throughput from {concurrency_report}"
        )
    process_fps = float(process_row.group(1))
    measured_ms = DEFAULT_WORKERS_COUNT * MILLISECONDS_PER_SECOND / process_fps
    required_cores = (
        max_supported
        / args.interval
        * measured_ms
        / MILLISECONDS_PER_SECOND
        * CAPACITY_HEADROOM_MULTIPLIER
    )

    lines = [
        f"# Load test — {date.today().isoformat()}",
        "",
        f"- Clip: `{args.clip}`",
        f"- Interval: {args.interval}s; duration per level: {args.duration}s",
        f"- Unique JPEG frames in clip: {len(frames)}; the clip is replayed cyclically.",
        f"- Workers: {args.workers}; queue size: {args.queue_size}; stale age: {args.max_frame_age}s",
        "- Workers were started and warm-up inference completed before measured runs.",
        "- Latency measures submission-to-inference-result; it does not include a web/API server.",
        "",
        "| Students | Submitted | Completed | Dropped | Drop rate | p50 ms | p95 ms | p99 ms |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        f"| {r['students']} | {r['submitted']} | {r['completed']} | {r['dropped']} | "
        f"{r['drop_rate']:.2%} | {r['p50_ms']:.2f} | {r['p95_ms']:.2f} | {r['p99_ms']:.2f} |"
        for r in reports
    )
    lines += [
        "",
        f"- `frames_dropped_stale`: {stale_drops}",
        f"- Maximum tested student count with p95 under 2s: {max_supported}",
        f"- Measured 4-process per-worker service time from concurrency benchmark: "
        f"{measured_ms:.3f} ms/frame ({process_fps:.3f} aggregate frames/s)",
        f"- Capacity formula at {max_supported} students: "
        f"`{max_supported} / {args.interval} × {measured_ms:.3f} / 1000 × 2 ≈ {required_cores:.3f} cores` "
        f"(approximate; based on this machine and clip)",
        "- Maximum student count requires both p95 < 2s and zero dropped frames in the tested run.",
        "- This exploratory run used 10s per student-count level, not the planned 120s soak; "
        "only 14 unique frames from one clip were replayed. Do not use it as production capacity evidence.",
    ]
    report = "\n".join(lines) + "\n"
    output = (
        args.output or ROOT / "docs" / "benchmarks" / f"load_{date.today().isoformat()}.md"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
