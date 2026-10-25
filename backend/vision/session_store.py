"""Session state stores and per-session processing locks."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
import threading
import time
from typing import Iterator, Optional
from uuid import uuid4

from .event_builder import EventBuilder

DEFAULT_SESSION_TTL_SECONDS: float = 2.0 * 60.0 * 60.0  # 2 hours
DEFAULT_LOCK_TIMEOUT_SECONDS: float = 0.5

# Redis store constants
DEFAULT_REDIS_LOCK_LEASE_MS: int = 10_000
REDIS_LEASE_RENEWAL_RATIO: float = 3.0
REDIS_RETRY_SLEEP_SECONDS: float = 0.01
REDIS_DEFAULT_KEY_PREFIX: str = "cheat-vision:session:"
REDIS_DEFAULT_LOCK_DROP_KEY: str = "cheat-vision:frames_dropped_lock"

STORE_BACKEND_MEMORY: str = "memory"
STORE_BACKEND_REDIS: str = "redis"

LUA_RELEASE_LOCK: str = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) "
    "else return 0 end"
)
LUA_RENEW_LOCK: str = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('pexpire', KEYS[1], ARGV[2]) "
    "else return 0 end"
)


class SessionStore(ABC):
    """Abstract interface for session-scoped event builder state and locks."""

    @abstractmethod
    def load(self, session_id: int | str) -> Optional[EventBuilder]:
        """Load a session builder, or return None when it does not exist."""

    @abstractmethod
    def save(self, session_id: int | str, builder: EventBuilder) -> None:
        """Persist the builder's runtime state."""

    @abstractmethod
    def delete(self, session_id: int | str) -> None:
        """Remove the session state."""

    @abstractmethod
    def session_lock(
        self, session_id: int | str, timeout_s: float = DEFAULT_LOCK_TIMEOUT_SECONDS
    ) -> Iterator[bool]:
        """Acquire an exclusive lock for one session for the context duration."""

    @abstractmethod
    def record_lock_drop(self) -> None:
        """Increment the dropped-frame lock counter."""


@dataclass
class _LockEntry:
    lock: threading.Lock
    references: int
    touched_at: float


class InMemorySessionStore(SessionStore):
    """Single-process store with idle TTL eviction and per-session locks."""

    def __init__(self, ttl_s: float = DEFAULT_SESSION_TTL_SECONDS) -> None:
        self.ttl_s = ttl_s
        self._builders: dict[str, EventBuilder] = {}
        self._last_access: dict[str, float] = {}
        self._locks: dict[str, _LockEntry] = {}
        self._guard = threading.RLock()
        self.frames_dropped_lock = 0

    @staticmethod
    def _normalize_key(session_id: int | str) -> str:
        return str(session_id)

    def _purge_expired(self, current_time: float) -> None:
        """Evict sessions and stale locks that have exceeded idle TTL."""
        expired_sessions = [
            key
            for key, touched in self._last_access.items()
            if current_time - touched >= self.ttl_s
        ]
        for key in expired_sessions:
            self._builders.pop(key, None)
            self._last_access.pop(key, None)

        stale_locks = [
            key
            for key, entry in self._locks.items()
            if entry.references == 0 and current_time - entry.touched_at >= self.ttl_s
        ]
        for key in stale_locks:
            self._locks.pop(key, None)

    def load(self, session_id: int | str) -> Optional[EventBuilder]:
        key = self._normalize_key(session_id)
        current_time = time.monotonic()
        with self._guard:
            self._purge_expired(current_time)
            builder = self._builders.get(key)
            if builder is not None:
                self._last_access[key] = current_time
            return builder

    def save(self, session_id: int | str, builder: EventBuilder) -> None:
        key = self._normalize_key(session_id)
        current_time = time.monotonic()
        with self._guard:
            self._purge_expired(current_time)
            self._builders[key] = builder
            self._last_access[key] = current_time

    def delete(self, session_id: int | str) -> None:
        key = self._normalize_key(session_id)
        with self._guard:
            self._builders.pop(key, None)
            self._last_access.pop(key, None)

    @contextmanager
    def session_lock(
        self, session_id: int | str, timeout_s: float = DEFAULT_LOCK_TIMEOUT_SECONDS
    ) -> Iterator[bool]:
        key = self._normalize_key(session_id)
        current_time = time.monotonic()
        with self._guard:
            self._purge_expired(current_time)
            entry = self._locks.setdefault(
                key, _LockEntry(threading.Lock(), 0, current_time)
            )
            entry.references += 1
            entry.touched_at = current_time

        acquired = entry.lock.acquire(timeout=timeout_s)
        try:
            yield acquired
        finally:
            if acquired:
                entry.lock.release()
            with self._guard:
                entry.references -= 1
                entry.touched_at = time.monotonic()

    def record_lock_drop(self) -> None:
        with self._guard:
            self.frames_dropped_lock += 1


class RedisSessionStore(SessionStore):
    """Redis-backed serialized state and a short distributed lock per session."""

    def __init__(
        self,
        redis_url: str,
        ttl_s: int = int(DEFAULT_SESSION_TTL_SECONDS),
        redis_client: Optional[object] = None,
    ) -> None:
        if redis_client is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError(
                    "Redis session storage requires the optional 'redis' package"
                ) from exc
            redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._redis = redis_client
        self.ttl_s = ttl_s
        self._prefix = REDIS_DEFAULT_KEY_PREFIX
        self._lock_drop_key = REDIS_DEFAULT_LOCK_DROP_KEY

    def _state_key(self, session_id: int | str) -> str:
        return f"{self._prefix}{session_id}:state"

    def _lock_key(self, session_id: int | str) -> str:
        return f"{self._prefix}{session_id}:lock"

    def load(self, session_id: int | str) -> Optional[EventBuilder]:
        key = self._state_key(session_id)
        payload = self._redis.get(key)
        if payload is None:
            return None
        self._redis.expire(key, self.ttl_s)
        return EventBuilder.from_state(json.loads(payload))

    def save(self, session_id: int | str, builder: EventBuilder) -> None:
        payload = json.dumps(builder.state_dict(), separators=(",", ":"))
        self._redis.set(self._state_key(session_id), payload, ex=self.ttl_s)

    def delete(self, session_id: int | str) -> None:
        self._redis.delete(self._state_key(session_id))

    @contextmanager
    def session_lock(
        self, session_id: int | str, timeout_s: float = DEFAULT_LOCK_TIMEOUT_SECONDS
    ) -> Iterator[bool]:
        key = self._lock_key(session_id)
        token = uuid4().hex
        deadline = time.monotonic() + timeout_s
        acquired = False

        while time.monotonic() < deadline:
            if self._redis.set(key, token, nx=True, px=DEFAULT_REDIS_LOCK_LEASE_MS):
                acquired = True
                break
            remaining_time = deadline - time.monotonic()
            time.sleep(min(REDIS_RETRY_SLEEP_SECONDS, max(0.0, remaining_time)))

        stop_renewal = threading.Event()
        renewal_thread: Optional[threading.Thread] = None

        if acquired:
            renewal_interval = DEFAULT_REDIS_LOCK_LEASE_MS / (REDIS_LEASE_RENEWAL_RATIO * 1000.0)

            def renew_lease() -> None:
                while not stop_renewal.wait(renewal_interval):
                    success = self._redis.eval(
                        LUA_RENEW_LOCK, 1, key, token, DEFAULT_REDIS_LOCK_LEASE_MS
                    )
                    if not success:
                        return

            renewal_thread = threading.Thread(target=renew_lease, daemon=True)
            renewal_thread.start()

        try:
            yield acquired
        finally:
            if acquired:
                stop_renewal.set()
                if renewal_thread is not None:
                    renewal_thread.join(timeout=0.1)
                self._redis.eval(LUA_RELEASE_LOCK, 1, key, token)

    def record_lock_drop(self) -> None:
        self._redis.incr(self._lock_drop_key)

    @property
    def frames_dropped_lock(self) -> int:
        return int(self._redis.get(self._lock_drop_key) or 0)


_global_store: Optional[SessionStore] = None
_store_guard = threading.Lock()


def get_session_store() -> SessionStore:
    """Create the configured store lazily from VISION_SESSION_STORE."""
    global _global_store
    if _global_store is None:
        with _store_guard:
            if _global_store is None:
                backend = os.getenv("VISION_SESSION_STORE", STORE_BACKEND_MEMORY).strip().lower()
                if backend == STORE_BACKEND_MEMORY:
                    _global_store = InMemorySessionStore()
                elif backend == STORE_BACKEND_REDIS:
                    redis_url = os.getenv("VISION_REDIS_URL")
                    if not redis_url:
                        raise ValueError(
                            "VISION_REDIS_URL is required when VISION_SESSION_STORE=redis"
                        )
                    _global_store = RedisSessionStore(redis_url)
                else:
                    raise ValueError(
                        f"VISION_SESSION_STORE must be '{STORE_BACKEND_MEMORY}' or '{STORE_BACKEND_REDIS}'"
                    )
    return _global_store


def set_session_store(store: Optional[SessionStore]) -> None:
    """Replace the process store; exposed for application wiring and tests."""
    global _global_store
    with _store_guard:
        _global_store = store
