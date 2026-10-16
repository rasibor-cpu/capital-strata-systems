"""Single-flight coordination for Questrade OAuth refresh (H2 hardening).

Questrade refresh tokens are single-use: two callers that POST the same refresh token
race, and the loser is told the authorization was revoked. This module provides:

  * an in-process lock registry keyed by the token store's coordination key, and
  * an inter-process advisory file lock (fcntl on POSIX, msvcrt on Windows; stdlib only)
    with a bounded acquisition timeout.

OS advisory locks are released by the kernel when the holding process dies, so a lock
file left behind by a crashed process is "stale" by construction: it is simply re-acquired
(its recorded owner metadata is informational only). A lock that is *held* is never
broken; acquisition times out and the refresh fails closed without any network call.

No token material ever passes through this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import threading
import time
import uuid
from typing import Any, Callable

from backend.brokers.questrade.errors import TokenStoreError

_REGISTRY_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.Lock] = {}

DEFAULT_LOCK_TIMEOUT_SECONDS = 30.0
_POLL_SECONDS = 0.05


def coordination_key(store: Any) -> str:
    getter = getattr(store, "coordination_key", None)
    if callable(getter):
        return str(getter())
    # Stores without a durable identity get a unique per-object key. id() alone could be
    # recycled after garbage collection and must never route one store's pending token to another.
    existing = getattr(store, "_css_refresh_coordination_key", None)
    if isinstance(existing, str):
        return existing
    key = f"object:{uuid.uuid4().hex}"
    try:
        setattr(store, "_css_refresh_coordination_key", key)
    except Exception:
        key = f"object:{id(store)}"
    return key


def thread_lock_for(key: str) -> threading.Lock:
    with _REGISTRY_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = _THREAD_LOCKS[key] = threading.Lock()
        return lock


class RefreshLockTimeout(TokenStoreError):
    def __init__(self) -> None:
        super().__init__("QUESTRADE_REFRESH_LOCK_TIMEOUT", code="QUESTRADE_REFRESH_LOCK_TIMEOUT")


@dataclass
class InterProcessFileLock:
    """Exclusive advisory lock on ``path``. Use as a context manager."""

    path: Path
    timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self._fd: int | None = None
        self.reclaimed_stale = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists() and self.path.stat().st_size > 0
        fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o600)
        deadline = self.clock() + max(0.0, float(self.timeout_seconds))
        try:
            while True:
                if _try_lock(fd):
                    break
                if self.clock() >= deadline:
                    raise RefreshLockTimeout()
                self.sleeper(_POLL_SECONDS)
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        # Lock file left by a dead holder: the OS already released it, we now own it.
        self.reclaimed_stale = existed
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0) if os.name != "nt" else None
            os.write(fd, f"pid={os.getpid()} acquired_unix={int(time.time())}\n".encode("ascii"))
        except OSError:
            pass  # owner metadata is informational only

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            _unlock(fd)
        finally:
            os.close(fd)

    def __enter__(self) -> "InterProcessFileLock":
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


if os.name == "nt":  # pragma: no cover - exercised by Windows CI
    import msvcrt

    def _try_lock(fd: int) -> bool:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(fd: int) -> None:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (BlockingIOError, PermissionError):
            return False

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


class _NullLock:
    reclaimed_stale = False

    def __enter__(self) -> "_NullLock":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def process_lock_for(store: Any, *, timeout_seconds: float) -> Any:
    getter = getattr(store, "lock_path", None)
    if not callable(getter):
        return _NullLock()  # in-memory stores: thread lock alone is sufficient
    return InterProcessFileLock(Path(getter()), timeout_seconds=timeout_seconds)


__all__ = [
    "DEFAULT_LOCK_TIMEOUT_SECONDS",
    "InterProcessFileLock",
    "RefreshLockTimeout",
    "coordination_key",
    "process_lock_for",
    "thread_lock_for",
]
