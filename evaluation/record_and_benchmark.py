"""Utility to record evaluation test clips while benchmarking analyze_frame() latency."""

from pathlib import Path
import platform
import sys
import time
from typing import List, Optional, Tuple
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.vision.pipeline import analyze_frame

CLIPS_DIR: Path = Path(__file__).resolve().parent / "clips"
DEFAULT_FPS: float = 20.0
WARMUP_MAX_READS: int = 30
SENSOR_WARMUP_SLEEP_SECONDS: float = 0.05
MILLISECONDS_PER_SECOND: float = 1000.0


def open_webcam_with_warmup(preferred_index: int = 0) -> Tuple[cv2.VideoCapture, np.ndarray]:
    """Open webcam trying DirectShow first on Windows, polling until valid frames return."""
    is_windows = platform.system() == "Windows"
    apis = [cv2.CAP_DSHOW, cv2.CAP_MSMF] if is_windows else [cv2.CAP_ANY]
    indices = [preferred_index] + ([1, 0] if preferred_index not in (0, 1) else [1 - preferred_index])

    for idx in indices:
        for api in apis:
            cap = cv2.VideoCapture(idx, api)
            if not cap.isOpened():
                cap.release()
                continue

            # Allow camera hardware sensor to warm up and discard initial blank frames
            for _ in range(WARMUP_MAX_READS):
                ok, frame = cap.read()
                if ok and frame is not None and frame.size > 0:
                    print(f"[INFO] Webcam opened successfully (index={idx}, backend={api}).")
                    return cap, frame
                time.sleep(SENSOR_WARMUP_SLEEP_SECONDS)

            cap.release()

    raise RuntimeError(
        "Could not read frames from any webcam (indices 0, 1). "
        "Make sure 'probe.py', browsers, or other camera apps are completely closed."
    )


def record_and_benchmark(clip_filename: str, camera_index: int = 0) -> None:
    """Record a webcam clip and measure per-frame inference latency once per second."""
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CLIPS_DIR / clip_filename

    if output_path.exists():
        output_path.unlink()

    cap, first_frame = open_webcam_with_warmup(camera_index)
    height, width = first_frame.shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, DEFAULT_FPS, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Failed to initialize VideoWriter for: {output_path}")

    latencies_ms: List[float] = []
    frame_idx = 0
    sample_step = int(DEFAULT_FPS)

    print(f"Recording started -> {output_path} ({width}x{height} @ {DEFAULT_FPS} FPS)")
    print("Press 'q' or ESC inside the camera window to stop and save.")

    try:
        frame: Optional[np.ndarray] = first_frame
        while frame is not None:
            writer.write(frame)

            if frame_idx % sample_step == 0:
                timestamp = frame_idx / DEFAULT_FPS
                ok_enc, buffer = cv2.imencode(".jpg", frame)
                if ok_enc:
                    image_bytes = buffer.tobytes()
                    start_t = time.perf_counter()
                    signals = analyze_frame(image_bytes, timestamp)
                    elapsed_ms = (time.perf_counter() - start_t) * MILLISECONDS_PER_SECOND
                    latencies_ms.append(elapsed_ms)
                    print(
                        f"t={timestamp:5.1f}s | latency={elapsed_ms:6.2f} ms | "
                        f"signals={signals}"
                    )

            cv2.imshow("Recording & Benchmarking (Press 'q' to stop)", cv2.flip(frame, 1))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break

            ok, next_frame = cap.read()
            if not ok:
                break
            frame = next_frame
            frame_idx += 1
    finally:
        cap.release()
        writer.release()
        cv2.destroyAllWindows()

    file_size_kb = output_path.stat().st_size / 1024.0 if output_path.exists() else 0.0
    if file_size_kb < 1.0:
        raise RuntimeError(f"Recording failed: {output_path} is empty ({file_size_kb:.2f} KB).")

    if latencies_ms:
        steady_latencies = latencies_ms[1:] if len(latencies_ms) > 1 else latencies_ms
        avg_ms = sum(steady_latencies) / len(steady_latencies)
        max_ms = max(steady_latencies)
        print("\n--- Benchmark Summary ---")
        print(f"Saved video      : {output_path} ({file_size_kb:.1f} KB)")
        print(f"Frames recorded  : {frame_idx + 1}")
        print(f"Frames analyzed  : {len(latencies_ms)}")
        print(f"Cold-start frame : {latencies_ms[0]:.2f} ms")
        print(f"Steady avg/frame : {avg_ms:.2f} ms")
        print(f"Steady max/frame : {max_ms:.2f} ms")


if __name__ == "__main__":
    target_name = sys.argv[1] if len(sys.argv) > 1 else "clip_01_normal.mp4"
    cam_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    record_and_benchmark(target_name, cam_idx)
