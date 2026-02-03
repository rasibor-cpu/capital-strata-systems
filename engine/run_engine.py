"""
engine/run_engine.py

Minimal dependency-light engine entrypoint for guarded runs.
This is intentionally NOT FastAPI.

Purpose:
- Provides a stable callable: main()
- Demonstrates kill-switch + heartbeat readiness
- Prevents freeze by returning control periodically
- Safe placeholder until you bind the real engine loop here
"""

from __future__ import annotations

import os
import time

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.kill_switch import assert_not_killed
from backend.app.observability.health import DEFAULT_HEARTBEAT

log = get_logger("engine.run_engine")


def main() -> None:
    adapter = with_trace(log, "ENGINE")
    adapter.info("ENGINE_ENTRYPOINT_START")

    # Heartbeat is safe even if adapters don't beat yet
    try:
        DEFAULT_HEARTBEAT.start()
    except Exception:
        # fail-safe: never block engine start due to heartbeat
        adapter.warning("HEARTBEAT_START_FAILED (suppressed)")

    # Minimal loop (placeholder). Replace this section with your real engine loop later.
    ticks = int(os.getenv("REA_ENGINE_TICKS", "20"))   # how many cycles before exit (for testing)
    sleep_s = float(os.getenv("REA_ENGINE_SLEEP_S", "0.5"))

    for i in range(ticks):
        if not assert_not_killed(pair="GLOBAL"):
            adapter.critical("ENGINE_STOP | reason=kill_switch_active")
            return

        adapter.info("ENGINE_TICK | i=%s/%s", i + 1, ticks)
        time.sleep(sleep_s)

    adapter.info("ENGINE_ENTRYPOINT_END")

