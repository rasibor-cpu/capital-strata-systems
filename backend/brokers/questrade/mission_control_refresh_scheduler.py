"""Bounded periodic refresh for explicitly activated Questrade Mission Control read-only evidence."""
from __future__ import annotations

from threading import Event, Lock, Thread
from typing import Any


class QuestradeMissionControlRefreshScheduler:
    """Refresh an already-activated coordinator without creating activation authority."""

    def __init__(
        self,
        coordinator: Any,
        *,
        interval_seconds: float = 60.0,
    ) -> None:
        self._coordinator = coordinator
        self._interval_seconds = max(1.0, float(interval_seconds))
        self._stop = Event()
        self._refresh_lock = Lock()
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def start(self) -> bool:
        if self.running:
            return False

        self._stop.clear()
        self._thread = Thread(
            target=self._run,
            name="css-questrade-readonly-refresh",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout_seconds)))

    def refresh_once(self) -> dict[str, Any]:
        """Refresh only when explicit activation has already reached READY."""
        status = self._coordinator.status()
        activated = bool(status.get("attempted")) and bool(
            status.get("provider_available")
        )
        if str(status.get("status") or "").upper() != "READY" and not activated:
            return {
                "status": "IDLE",
                "reason": "QUESTRADE_NOT_READY",
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            }

        if not self._refresh_lock.acquire(blocking=False):
            return {
                "status": "IDLE",
                "reason": "REFRESH_ALREADY_IN_PROGRESS",
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            }

        try:
            return dict(self._coordinator.refresh())
        finally:
            self._refresh_lock.release()

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self.refresh_once()
            except Exception:
                # Presentation retains R8.7 last-known evidence. The scheduler
                # must never terminate the launcher or create activation authority.
                continue


__all__ = ["QuestradeMissionControlRefreshScheduler"]
