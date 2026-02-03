"""
engine/run_engine.py

Minimal dependency-light engine entrypoint for guarded runs.

Now supports:
- READY state on boot
- Blocks for login credentials (AuthContext.user_id)
- Live arming latch (prevents accidental live)
- User-derived functionality: everything after login can key off user_id
"""

from __future__ import annotations

import os
import time

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.kill_switch import assert_not_killed
from backend.app.observability.health import DEFAULT_HEARTBEAT

from backend.app.security.auth_gate import await_login_ready_state, AuthContext
from backend.app.ops.live_arm import assert_live_armed_or_block

log = get_logger("engine.run_engine")


def _print_ready_instructions() -> None:
    print("")
    print("REA ENGINE READY")
    print("- Set REA_EXPECTED_AUTH_KEY to enable login gate.")
    print("- Login is required to proceed.")
    print("- For live test/live use: set REA_LIVE_ARM=1 and REA_CONFIRM_LIVE=YES")
    print("")


def main() -> None:
    adapter = with_trace(log, "ENGINE")
    adapter.info("ENGINE_ENTRYPOINT_START")

    # Heartbeat must never block startup
    try:
        DEFAULT_HEARTBEAT.start()
    except Exception:
        adapter.warning("HEARTBEAT_START_FAILED (suppressed)")

    # READY state + login gate
    _print_ready_instructions()
    login_timeout = int(os.getenv("REA_LOGIN_TIMEOUT_SECONDS", "0"))  # 0 = infinite
    auth: AuthContext = await_login_ready_state(timeout_s=login_timeout)

    # User context is now authoritative.
    # Everything after this point should use auth.user_id for routing/permissions/auditing.
    adapter.info("USER_CONTEXT | user_id=%s | method=%s", auth.user_id, auth.auth_method)

    # Live arming latch (does NOT prevent paper/backtest; only gates “live” intent)
    # If you want strict mode later, we can hard-block engine start when not armed.
    live_intent = os.getenv("REA_LIVE_INTENT", "").strip().lower()  # "live" | "paper" | ""
    if live_intent == "live":
        if not assert_live_armed_or_block():
            adapter.critical("ENGINE_BLOCK | reason=live_intent_not_armed")
            print("ENGINE BLOCKED: live intent requested but not armed.")
            return
        adapter.info("LIVE_INTENT_ARMED | user_id=%s", auth.user_id)
    else:
        adapter.info("LIVE_INTENT_NOT_REQUESTED | intent=%s", live_intent or "paper/default")

    # Minimal loop placeholder (safe). Replace with real engine loop later.
    ticks = int(os.getenv("REA_ENGINE_TICKS", "20"))
    sleep_s = float(os.getenv("REA_ENGINE_SLEEP_S", "0.5"))

    for i in range(ticks):
        if not assert_not_killed(pair="GLOBAL"):
            adapter.critical("ENGINE_STOP | reason=kill_switch_active")
            return

        adapter.info("ENGINE_TICK | user_id=%s | i=%s/%s", auth.user_id, i + 1, ticks)
        time.sleep(sleep_s)

    adapter.info("ENGINE_ENTRYPOINT_END")
