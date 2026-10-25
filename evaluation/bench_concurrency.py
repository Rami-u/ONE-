"""Measure inference throughput with one/four threads and four processes."""

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import date
import os
from pathlib import Path
import platform
import sys
import time
import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.vision.pipeline import analyze_frame
from backend.vision.worker import _warm_worker

DEFAULT_BENCHMARK_FRAMES: int = 14
DEFAULT_REPEAT_COUNT: int = 10
DEFAULT_WORKERS_COUNT: int = 4


def load_frames(path: Path, count: int) -> list[bytes]:
    """Read up to count frames from a video clip and encode each as JPEG bytes."""
    cap = cv2.VideoCapture(str(path))
    frames: list[bytes] = []
    try:
        while len(frames) < count:
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


def _process_infer(payload: tuple[bytes, float]):
    image, timestamp = payload
    return analyze_frame(image, timestamp)


def measure_threads(frames: list[bytes], workers: int) -> tuple[float, float]:
    """Measure inference throughput across worker threads."""
    jobs = [(frames[i % len(frames)], float(i)) for i in range(len(frames))]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_process_infer, jobs[:workers]))  # warm shared landmarker before timing
        started = time.perf_counter()
        list(pool.map(_process_infer, jobs))
        elapsed = time.perf_counter() - started
    return len(jobs) / elapsed, elapsed


def measure_processes(frames: list[bytes], workers: int = DEFAULT_WORKERS_COUNT) -> tuple[float, float]:
    """Measure inference throughput across worker processes with per-process warm-up."""
    jobs = [(frames[i % len(frames)], float(i)) for i in range(len(frames))]
    with ProcessPoolExecutor(
        max_workers=workers, initializer=_warm_worker, initargs=(frames[0],)
    ) as pool:
        # Force all worker processes to start and run initializer warm-up
        list(pool.map(abs, range(workers)))
        started = time.perf_counter()
        list(pool.map(_process_infer, jobs, chunksize=1))
        elapsed = time.perf_counter() - started
    return len(jobs) / elapsed, elapsed


def _get_processor_name() -> str:
    """Retrieve readable CPU description across operating systems."""
    cpu = os.getenv("PROCESSOR_IDENTIFIER", "")
    if platform.system() == "Windows":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
            winreg.CloseKey(key)
        except OSError:
            pass
    return cpu or platform.processor() or "unavailable"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clip",
        type=Path,
        default=ROOT / "evaluation" / "clips" / "clip_01_normal.mp4",
    )
    parser.add_argument("--frames", type=int, default=DEFAULT_BENCHMARK_FRAMES)
    parser.add_argument(
        "--repeat",
        type=int,
        default=DEFAULT_REPEAT_COUNT,
        help="repeat extracted frames to reduce short-sample noise",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be positive")

    frames = load_frames(args.clip, args.frames) * args.repeat
    results = [
        ("1 thread", *measure_threads(frames, 1)),
        ("4 threads", *measure_threads(frames, 4)),
        ("4 processes", *measure_processes(frames, 4)),
    ]
    cpu = _get_processor_name()

    lines = [
        f"# Concurrency benchmark — {date.today().isoformat()}",
        "",
        f"- CPU: {cpu}",
        f"- Logical CPUs: {os.cpu_count()}",
        f"- Input: `{args.clip.relative_to(ROOT) if args.clip.is_relative_to(ROOT) else args.clip}`",
        f"- Unique clip frames decoded: {len(frames) // args.repeat}",
        f"- JPEG frames measured after repeat: {len(frames)}",
        "",
        "| Mode | Throughput (frames/s) | Wall time (s) |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {name} | {rate:.3f} | {elapsed:.3f} |" for name, rate, elapsed in results
    )
    lines += [
        "",
        "The `FrameWorker` uses four processes so each worker owns an independent "
        "landmarker instance. On this run, four threads were faster than four processes; "
        "the small, repeated single-clip sample is not enough to generalize that result.",
        "",
        "Limitations: only 14 unique frames from one short normal clip were available; "
        "those frames were repeated to reach 70 measurements. Treat these results as a "
        "local smoke benchmark, not production capacity evidence.",
    ]
    report = "\n".join(lines) + "\n"
    print(report)

    output = (
        args.output
        or ROOT / "docs" / "benchmarks" / f"concurrency_{date.today().isoformat()}.md"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
