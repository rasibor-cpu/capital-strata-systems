from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any, Callable


_lock = Lock()
_stop = Event()
_heartbeat_at: datetime | None = None
_thread: Thread | None = None


def _run(interval_seconds: float) -> None:
    global _heartbeat_at
    while not _stop.wait(interval_seconds):
        with _lock:
            _heartbeat_at = datetime.now(timezone.utc)


def start_runtime_heartbeat(interval_seconds: float = 5.0) -> None:
    global _heartbeat_at, _thread
    with _lock:
        _heartbeat_at = datetime.now(timezone.utc)
        if _thread is not None and _thread.is_alive():
            return
        _stop.clear()
        _thread = Thread(
            target=_run,
            args=(float(interval_seconds),),
            name="css-runtime-heartbeat",
            daemon=True,
        )
        _thread.start()


def read_runtime_heartbeat() -> dict[str, str | None]:
    with _lock:
        heartbeat_at = _heartbeat_at
    return {
        "heartbeat_at": heartbeat_at.isoformat() if heartbeat_at else None,
        "heartbeat_source": "dashboard.runtime.runtime_heartbeat",
    }


# ---------------------------------------------------------------------------
# Endurance heartbeat publisher.
#
# The in-process heartbeat above only proves a thread is ticking. For an
# endurance run the supervised runtime also publishes, to a file the external
# monitor reads, two independent beat sequences -- a background thread
# (``thread_seq``) and the server's asyncio event loop (``loop_seq``) -- so a
# blocked event loop is distinguishable from a hung or dead process, plus a
# read-only safety-posture snapshot taken inside the runtime. Publishing is
# observation only; it changes no trading, broker or authority state.
# ---------------------------------------------------------------------------
HEARTBEAT_SCHEMA = "css.endurance_heartbeat.v1"
_pub_lock = Lock()
_pub_stop = Event()
_pub_thread: Thread | None = None
_pub: dict[str, Any] = {"thread_seq": 0, "loop_seq": 0, "loop_beat_monotonic": None}


def _publish_loop(path: str, interval_seconds: float, posture_fn: Callable[[], dict] | None, posture_every: int) -> None:
    from dashboard.runtime.endurance_evidence import atomic_write_json

    started_at = datetime.now(timezone.utc).isoformat()
    posture: dict[str, Any] | None = None
    posture_at: str | None = None
    posture_error: str | None = None
    while True:
        with _pub_lock:
            _pub["thread_seq"] += 1
            seq = _pub["thread_seq"]
            loop_seq = _pub["loop_seq"]
            loop_beat = _pub["loop_beat_monotonic"]
        if posture_fn is not None and (seq == 1 or seq % max(1, posture_every) == 0):
            try:
                posture = dict(posture_fn())
                posture_error = None
            except Exception as exc:  # recorded, never raised: a posture fault is evidence
                posture_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            posture_at = datetime.now(timezone.utc).isoformat()
        try:
            atomic_write_json(path, {
                "schema": HEARTBEAT_SCHEMA,
                "pid": os.getpid(),
                "started_at_utc": started_at,
                "wall_utc": datetime.now(timezone.utc).isoformat(),
                "monotonic": time.monotonic(),
                "interval_seconds": interval_seconds,
                "thread_seq": seq,
                "loop_seq": loop_seq,
                "loop_beat_monotonic": loop_beat,
                "posture": posture,
                "posture_at_utc": posture_at,
                "posture_error": posture_error,
            })
        except OSError:
            pass  # the monitor sees the sequence stop advancing
        if _pub_stop.wait(interval_seconds):
            return


async def event_loop_probe(interval_seconds: float = 5.0) -> None:
    """Advance ``loop_seq`` from inside the server's event loop. If a handler
    blocks the loop, this stops advancing while the thread beat continues."""
    while True:
        with _pub_lock:
            _pub["loop_seq"] += 1
            _pub["loop_beat_monotonic"] = time.monotonic()
        await asyncio.sleep(interval_seconds)


def start_heartbeat_publisher(
    path: str | os.PathLike[str],
    *,
    interval_seconds: float = 5.0,
    posture_fn: Callable[[], dict] | None = None,
    posture_every: int = 6,
) -> None:
    global _pub_thread
    with _pub_lock:
        if _pub_thread is not None and _pub_thread.is_alive():
            return
        _pub_stop.clear()
        _pub_thread = Thread(
            target=_publish_loop,
            args=(str(path), float(interval_seconds), posture_fn, int(posture_every)),
            name="css-endurance-heartbeat",
            daemon=True,
        )
        _pub_thread.start()


def stop_heartbeat_publisher() -> None:
    _pub_stop.set()


def register_stack_dump(path: str | os.PathLike[str]) -> bool:
    """Let the monitor request an all-threads stack dump (SIGUSR1) on a
    heartbeat loss. POSIX only; returns False where unsupported."""
    import faulthandler
    import signal

    if not hasattr(signal, "SIGUSR1"):
        return False
    handle = open(path, "a", encoding="utf-8")  # kept open for the process lifetime
    faulthandler.register(signal.SIGUSR1, file=handle, all_threads=True, chain=False)
    return True


__all__ = [
    "HEARTBEAT_SCHEMA", "event_loop_probe", "read_runtime_heartbeat", "register_stack_dump",
    "start_heartbeat_publisher", "start_runtime_heartbeat", "stop_heartbeat_publisher",
]