"""Process-based inference worker with bounded submission and stale-frame drops."""

from concurrent.futures import Future, ProcessPoolExecutor
import threading
import time
from typing import Optional

DEFAULT_MAX_WORKERS: int = 4
DEFAULT_QUEUE_SIZE: int = 16
DEFAULT_MAX_FRAME_AGE_SECONDS: float = 4.0


class BackpressureError(RuntimeError):
    """Raised when the bounded worker queue has no capacity."""


class StaleFrameError(RuntimeError):
    """Raised when a submitted frame expires before a worker can process it."""


def _warm_worker(sample_bytes: bytes) -> None:
    from .pipeline import analyze_frame

    analyze_frame(sample_bytes, 0.0)


def _run_inference(
    image_bytes: bytes,
    submitted_at: float,
    max_frame_age_s: float,
    server_ts: float,
) -> Optional[object]:
    """Execute inference if frame is not stale; returns None if frame expired."""
    if time.monotonic() - submitted_at > max_frame_age_s:
        return None
    from .pipeline import analyze_frame

    return analyze_frame(image_bytes, server_ts)


def _ping_worker() -> bool:
    return True


class FrameWorker:
    """A pool whose processes each initialize and warm their own landmarker."""

    def __init__(
        self,
        sample_bytes: bytes,
        max_workers: int = DEFAULT_MAX_WORKERS,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        max_frame_age_s: float = DEFAULT_MAX_FRAME_AGE_SECONDS,
    ) -> None:
        if max_workers < 1 or queue_size < 0 or max_frame_age_s <= 0:
            raise ValueError(
                "max_workers and max_frame_age_s must be positive; "
                "queue_size cannot be negative"
            )
        self.max_frame_age_s = max_frame_age_s
        self._capacity = threading.BoundedSemaphore(max_workers + queue_size)
        self._counter_lock = threading.Lock()
        self.frames_dropped_stale = 0
        self._executor = ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_warm_worker,
            initargs=(sample_bytes,),
        )
        self.max_workers = max_workers
        self._closed = False
        # Warm worker processes upfront before any session submits frames.
        self.warmup()

    def warmup(self) -> None:
        """Start all worker processes and wait for their initializer warm-ups."""
        if self._closed:
            raise RuntimeError("FrameWorker is shut down")
        futures = [
            self._executor.submit(_ping_worker) for _ in range(self.max_workers)
        ]
        for future in futures:
            future.result()

    def submit(
        self, session_id: int | str, image_bytes: bytes, server_ts: float
    ) -> Future:
        """Submit one frame; Future resolves to signals or raises on stale/backpressure."""
        _ = session_id, server_ts  # Contract metadata retained for telemetry/dispatch
        future: Future = Future()
        if self._closed:
            future.set_exception(RuntimeError("FrameWorker is shut down"))
            return future

        if not self._capacity.acquire(blocking=False):
            future.set_exception(BackpressureError("FrameWorker queue is full"))
            return future

        submitted_at = time.monotonic()
        try:
            task = self._executor.submit(
                _run_inference,
                image_bytes,
                submitted_at,
                self.max_frame_age_s,
                server_ts,
            )
        except BaseException:
            self._capacity.release()
            raise

        def on_task_completed(completed_task: Future) -> None:
            self._capacity.release()
            try:
                inference_result = completed_task.result()
                if inference_result is None:
                    with self._counter_lock:
                        self.frames_dropped_stale += 1
                    future.set_exception(
                        StaleFrameError("Frame expired before inference started")
                    )
                else:
                    future.set_result(inference_result)
            except BaseException as exc:
                future.set_exception(exc)

        task.add_done_callback(on_task_completed)
        return future

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the underlying executor and release resources."""
        self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def __enter__(self) -> "FrameWorker":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()
