"""Cross-platform exclusive interprocess file lock (CSS-065). Standard library only.

Backends (selected once, at import time):
- POSIX:   ``fcntl.flock(fd, LOCK_EX | LOCK_NB)``  (whole-file advisory lock)
- Windows: ``msvcrt.locking(fd, LK_NBLCK, 1)`` on byte 0 of the lock file (mandatory
  byte-range lock)

Both locks belong to the open file handle and are released by the operating system
when the handle is closed or the owning process dies, so a crashed holder can never
leave a stale lock behind (no lock-file deletion or PID heuristics are involved).
Every acquisition opens its own handle, so threads in one process exclude each other
exactly like separate processes do.

Acquisition polls non-blockingly until ``timeout_seconds`` elapses and then raises
``InterprocessLockTimeout``. Any error that is not plain lock contention is
re-raised unchanged. Callers must treat both as "operation not performed" (fail
closed). The lock file is never written to, truncated or deleted.
"""
from __future__ import annotations

import errno
import os
import sys
import time
from contextlib import contextmanager
from typing import Iterator

if sys.platform == "win32":
    import msvcrt

    LOCK_BACKEND = "msvcrt"
    _CONTENTION_ERRNOS = frozenset({errno.EACCES, getattr(errno, "EDEADLOCK", errno.EDEADLK), errno.EDEADLK})

    def _try_lock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    LOCK_BACKEND = "fcntl"
    _CONTENTION_ERRNOS = frozenset({errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES})

    def _try_lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_POLL_SECONDS = 0.02


class InterprocessLockTimeout(TimeoutError):
    """The lock could not be acquired within the timeout. Nothing was done under it."""


def _is_contention(exc: OSError) -> bool:
    return isinstance(exc, BlockingIOError) or exc.errno in _CONTENTION_ERRNOS


@contextmanager
def exclusive_file_lock(
    path: str | os.PathLike[str],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> Iterator[None]:
    """Hold an exclusive cross-process lock on ``path`` for the duration of the block."""
    if not timeout_seconds > 0 or not poll_seconds > 0:
        raise ValueError("timeout_seconds and poll_seconds must be positive")
    fd = os.open(os.fspath(path), os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o600)
    try:
        deadline = time.monotonic() + float(timeout_seconds)
        while True:
            try:
                _try_lock(fd)
                break
            except OSError as exc:
                if not _is_contention(exc):
                    raise
                if time.monotonic() >= deadline:
                    raise InterprocessLockTimeout(
                        f"could not lock {os.fspath(path)} within {timeout_seconds}s ({LOCK_BACKEND})"
                    ) from None
                time.sleep(poll_seconds)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
