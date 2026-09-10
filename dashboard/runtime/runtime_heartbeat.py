from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Lock, Thread


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


__all__ = ["read_runtime_heartbeat", "start_runtime_heartbeat"]