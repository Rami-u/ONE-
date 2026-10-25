import threading
import time
import pytest

from backend.vision.event_builder import EventBuilder
from backend.vision.session_store import InMemorySessionStore, RedisSessionStore


def create_signals(face_missing: bool = True) -> dict[str, object]:
    """Helper to generate mock signals for session store tests."""
    return {
        "face_count": 0 if face_missing else 1,
        "looking_away": False,
        "phone_detected": False,
    }


def test_event_builder_state_round_trip_preserves_behavior():
    original = EventBuilder()
    for timestamp in range(4):
        original.update(create_signals(face_missing=True), float(timestamp))

    restored = EventBuilder.from_state(original.state_dict())
    assert restored.state_dict() == original.state_dict()

    original_closed = original.update(create_signals(face_missing=False), 4.0)
    restored_closed = restored.update(create_signals(face_missing=False), 4.0)
    assert restored_closed == original_closed
    assert restored.state_dict() == original.state_dict()


def test_in_memory_store_evicts_idle_sessions_by_ttl():
    store = InMemorySessionStore(ttl_s=0.03)
    store.save("idle-session", EventBuilder())
    assert store.load("idle-session") is not None

    time.sleep(0.04)
    assert store.load("idle-session") is None


def test_same_session_critical_sections_do_not_interleave():
    store = InMemorySessionStore()
    active_workers_count = 0
    max_concurrent_workers = 0
    count_guard = threading.Lock()
    sync_barrier = threading.Barrier(3)

    def worker_task() -> None:
        nonlocal active_workers_count, max_concurrent_workers
        sync_barrier.wait()
        with store.session_lock("shared-session", timeout_s=0.5) as acquired:
            assert acquired
            with count_guard:
                active_workers_count += 1
                max_concurrent_workers = max(max_concurrent_workers, active_workers_count)
            time.sleep(0.03)
            with count_guard:
                active_workers_count -= 1

    threads = [threading.Thread(target=worker_task) for _ in range(2)]
    for thread in threads:
        thread.start()
    sync_barrier.wait()
    for thread in threads:
        thread.join()

    assert max_concurrent_workers == 1


def test_lock_times_out_when_another_request_holds_session():
    store = InMemorySessionStore()
    lock_entered = threading.Event()
    release_signal = threading.Event()

    def lock_holder() -> None:
        with store.session_lock("held-session") as acquired:
            assert acquired
            lock_entered.set()
            release_signal.wait(timeout=1.0)

    holder_thread = threading.Thread(target=lock_holder)
    holder_thread.start()
    assert lock_entered.wait(timeout=1.0)

    with store.session_lock("held-session", timeout_s=0.02) as acquired:
        assert not acquired

    release_signal.set()
    holder_thread.join()


@pytest.mark.integration
def test_redis_store_round_trip_when_fakeredis_is_available():
    fakeredis = pytest.importorskip("fakeredis")
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisSessionStore("redis://unused", redis_client=client)

    builder = EventBuilder()
    builder.update(create_signals(face_missing=True), 0.0)
    store.save("redis-session", builder)

    restored = store.load("redis-session")
    assert restored is not None
    assert restored.state_dict() == builder.state_dict()
