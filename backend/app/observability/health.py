"""
Health & Liveness Signals
REA Capital Trading Engine

Goals:
- Engine heartbeat (periodic "I'm alive" logs)
- Adapter heartbeat registry (detect silent failures)
- Zero coupling to strategy / execution
- Safe to import anywhere, safe to ignore if unused
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from backend.app.observability.logger import get_logger, with_trace

log = get_logger("observability.health")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AdapterStatus:
    name: str
    last_heartbeat_utc: datetime
    last_note: str = ""


class AdapterHeartbeatRegistry:
    """
    In-memory adapter heartbeat registry.
    Each adapter (or data source) can call .beat(name, note=...).

    This module does not assume adapters exist; it simply provides a registry.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status: Dict[str, AdapterStatus] = {}

    def beat(self, name: str, note: str = "") -> None:
        if not name or not isinstance(name, str):
            return  # fail-safe: do not break the engine on bad adapter names
        with self._lock:
            self._status[name] = AdapterStatus(
                name=name,
                last_heartbeat_utc=_utc_now(),
                last_note=note or "",
            )

    def snapshot(self) -> Dict[str, AdapterStatus]:
        with self._lock:
            return dict(self._status)

    def stale_adapters(self, stale_after_seconds: int) -> Dict[str, AdapterStatus]:
        """
        Return adapters whose last heartbeat is older than stale_after_seconds.
        """
        now = _utc_now()
        out: Dict[str, AdapterStatus] = {}
        with self._lock:
            for name, st in self._status.items():
                age = (now - st.last_heartbeat_utc).total_seconds()
                if age > float(stale_after_seconds):
                    out[name] = st
        return out


class EngineHeartbeat:
    """
    Periodic liveness logger. Runs in a daemon thread.

    It logs:
      - engine uptime
      - known adapter count
      - stale adapter list (if any)
    """

    def __init__(
        self,
        registry: Optional[AdapterHeartbeatRegistry] = None,
        interval_seconds: int = 30,
        adapter_stale_after_seconds: int = 120,
        warn_on_no_adapters: bool = True,
    ) -> None:
        self.registry = registry or AdapterHeartbeatRegistry()
        self.interval_seconds = int(max(5, interval_seconds))
        self.adapter_stale_after_seconds = int(max(10, adapter_stale_after_seconds))
        self.warn_on_no_adapters = bool(warn_on_no_adapters)

        self._start_utc = _utc_now()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="engine-heartbeat", daemon=True)
        self._thread.start()

        adapter = with_trace(log, "HEARTBEAT")
        adapter.info("EngineHeartbeat started | interval=%ss | stale_after=%ss",
                     self.interval_seconds, self.adapter_stale_after_seconds)

    def stop(self, timeout_seconds: int = 2) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=float(timeout_seconds))

        adapter = with_trace(log, "HEARTBEAT")
        adapter.info("EngineHeartbeat stopped")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._emit()
            except Exception as e:
                # hard fail-safe: heartbeat must never crash the engine
                adapter = with_trace(log, "HEARTBEAT")
                adapter.error("Heartbeat error suppressed | %s", str(e))
            time.sleep(self.interval_seconds)

    def _emit(self) -> None:
        now = _utc_now()
        uptime_s = int((now - self._start_utc).total_seconds())

        snap = self.registry.snapshot()
        adapter_count = len(snap)

        stale = self.registry.stale_adapters(self.adapter_stale_after_seconds)
        stale_list = ",".join(sorted(stale.keys())) if stale else ""

        adapter = with_trace(log, "HEARTBEAT")

        # Silent failure detection:
        # - If we expect adapters but none are beating, warn (configurable).
        if adapter_count == 0 and self.warn_on_no_adapters:
            adapter.warning(
                "ENGINE_HEARTBEAT | uptime=%ss | adapters=0 | state=AMBER(no_adapter_heartbeats)",
                uptime_s,
            )
            return

        if stale:
            adapter.warning(
                "ENGINE_HEARTBEAT | uptime=%ss | adapters=%s | state=AMBER(stale_adapters) | stale=%s",
                uptime_s,
                adapter_count,
                stale_list,
            )
            return

        adapter.info(
            "ENGINE_HEARTBEAT | uptime=%ss | adapters=%s | state=GREEN",
            uptime_s,
            adapter_count,
        )


# Convenience singletons (optional usage)
DEFAULT_REGISTRY = AdapterHeartbeatRegistry()
DEFAULT_HEARTBEAT = EngineHeartbeat(registry=DEFAULT_REGISTRY)
