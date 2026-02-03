"""
run_live_guarded.py

Guarded live runner for REA Capital Trading Engine.

Key protections:
- Token validation hook (confirm-token step)
- Global + pair kill-switch checks (env + runtime file)
- Watchdog timeout wrapper to prevent "freeze while processing"
- Clean CTRL+C exit
- Fail-closed session gating stubs (optional)

This file is designed to be a SAFE wrapper. It should not break any adapters.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Any

# Observability modules (added earlier)
from backend.app.observability.logger import init_logging, get_logger, with_trace, log_startup_banner
from backend.app.observability.kill_switch import assert_not_killed
from backend.app.observability.session_time import assert_session_allowed

log = get_logger("run_live_guarded")


# -----------------------------
# Config
# -----------------------------

DEFAULT_COMMAND_TIMEOUT_SECONDS = int(os.getenv("REA_COMMAND_TIMEOUT_SECONDS", "45"))
DEFAULT_ASSET_CLASS = os.getenv("REA_ASSET_CLASS", "fx")  # fx | crypto | equities | options


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str
    elapsed_s: float = 0.0


# -----------------------------
# Token Validation Hook (pluggable)
# -----------------------------

def validate_token_or_fail() -> GuardResult:
    """
    Hook point: confirm-token validation.
    If you already have engine/execution/confirm_token.py, we import and call it.
    If not present, we fail CLOSED in live mode only.

    This is intentionally conservative.
    """
    start = time.time()
    adapter = with_trace(log, "TOKEN")

    try:
        # If your confirm_token.py exposes a function, call it.
        # We try common names; you can standardize later.
        from engine.execution.confirm_token import validate_token  # type: ignore
        ok = bool(validate_token())
        if ok:
            adapter.info("TOKEN_OK")
            return GuardResult(True, "token_ok", time.time() - start)
        adapter.warning("TOKEN_FAIL")
        return GuardResult(False, "token_fail", time.time() - start)

    except Exception as e:
        # Fail-closed if token module not available
        adapter.error("TOKEN_CHECK_ERROR | %s", str(e))
        return GuardResult(False, "token_check_error_or_missing", time.time() - start)


# -----------------------------
# Timeout Watchdog (prevents freezes)
# -----------------------------

class TimeoutError(Exception):
    pass


def run_with_timeout(fn: Callable[[], Any], timeout_s: int, trace_id: str) -> Any:
    """
    Runs fn() in a thread and raises TimeoutError if not completed in timeout_s.
    This does NOT kill the process thread forcibly (Python can't safely),
    but it prevents the runner from waiting forever and enables a controlled shutdown.

    Combined with kill-switch checks, the next loop will stop.
    """
    result_container = {"done": False, "value": None, "err": None}

    def _target():
        try:
            result_container["value"] = fn()
        except Exception as e:
            result_container["err"] = e
        finally:
            result_container["done"] = True

    t = threading.Thread(target=_target, daemon=True)
    t.start()

    start = time.time()
    while time.time() - start < timeout_s:
        if result_container["done"]:
            if result_container["err"] is not None:
                raise result_container["err"]
            return result_container["value"]
        time.sleep(0.05)

    raise TimeoutError(f"command_timeout_after_{timeout_s}s")


# -----------------------------
# Clean shutdown handling
# -----------------------------

_STOP = {"requested": False}


def _handle_sigint(signum, frame):
    _STOP["requested"] = True
    adapter = with_trace(log, "STOP")
    adapter.warning("STOP_REQUESTED | signal=SIGINT")


def stop_requested() -> bool:
    return bool(_STOP["requested"])


# -----------------------------
# Guarded Command Runner
# -----------------------------

def guarded_step(step_name: str, fn: Callable[[], Any], timeout_s: int) -> GuardResult:
    """
    Runs one guarded step:
    - kill switch check (pre)
    - session allowed check (pre)
    - timeout watchdog
    - kill switch check (post)
    """
    adapter = with_trace(log, f"STEP:{step_name}")
    start = time.time()

    # STOP request check
    if stop_requested():
        adapter.warning("STEP_ABORT | reason=stop_requested")
        return GuardResult(False, "stop_requested", time.time() - start)

    # Kill switch (global/pair)
    if not assert_not_killed(pair="GLOBAL"):
        adapter.critical("STEP_BLOCK | reason=kill_switch_active(pre)")
        return GuardResult(False, "kill_switch_active_pre", time.time() - start)

    # Session gating (fail-closed for asset classes not whitelisted)
    decision = assert_session_allowed(asset_class=DEFAULT_ASSET_CLASS, hard_fail=True)
    if not decision.allowed:
        adapter.warning("STEP_BLOCK | reason=session_blocked | state=%s | detail=%s", decision.state, decision.reason)
        return GuardResult(False, f"session_blocked:{decision.reason}", time.time() - start)

    # Execute with timeout
    try:
        run_with_timeout(fn, timeout_s=timeout_s, trace_id=f"STEP:{step_name}")
    except TimeoutError as te:
        adapter.critical("STEP_TIMEOUT | %s", str(te))
        return GuardResult(False, "timeout", time.time() - start)
    except Exception as e:
        adapter.error("STEP_ERROR | %s", str(e))
        return GuardResult(False, "exception", time.time() - start)

    # Kill switch post-check (so we don't proceed into next step)
    if not assert_not_killed(pair="GLOBAL"):
        adapter.critical("STEP_BLOCK | reason=kill_switch_active(post)")
        return GuardResult(False, "kill_switch_active_post", time.time() - start)

    adapter.info("STEP_OK | elapsed=%.2fs", time.time() - start)
    return GuardResult(True, "ok", time.time() - start)


# -----------------------------
# Main flow
# -----------------------------

def main() -> int:
    init_logging(os.getenv("LOG_LEVEL", "INFO"))
    log_startup_banner(log)

    # signal handler for CTRL+C
    signal.signal(signal.SIGINT, _handle_sigint)

    adapter = with_trace(log, "MAIN")
    adapter.info("RUN_LIVE_GUARDED_START | timeout=%ss | asset_class=%s", DEFAULT_COMMAND_TIMEOUT_SECONDS, DEFAULT_ASSET_CLASS)

    # Step A: Token validation (fail-closed)
    token_res = guarded_step("token_validation", validate_token_or_fail, timeout_s=15)
    if not token_res.ok:
        adapter.critical("ABORT | token step failed | reason=%s", token_res.reason)
        return 2

    # Step B: Your engine start hook (pluggable)
    def _start_engine():
        """
        Hook point: call your engine runner.
        Update import path to your real entrypoint when ready.
        """
        try:
            # If you have a canonical runner, call it here.
            # Example placeholder:
            from engine.execution.notify_outbox import flush_outbox  # type: ignore
            flush_outbox()  # harmless preflight if present
        except Exception:
            pass

        # Placeholder: simulate "engine running" loop.
        # Replace with your actual engine loop start.
        for _ in range(3):
            if stop_requested():
                return
            if not assert_not_killed(pair="GLOBAL"):
                return
            time.sleep(0.25)

    eng_res = guarded_step("engine_start", _start_engine, timeout_s=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    if not eng_res.ok:
        adapter.critical("ABORT | engine start failed | reason=%s", eng_res.reason)
        return 3

    adapter.info("RUN_LIVE_GUARDED_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
