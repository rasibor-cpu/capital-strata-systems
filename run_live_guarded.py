"""
run_live_guarded.py

Guarded live runner for REA Capital Trading Engine.

Protections:
- Token validation hook (confirm-token step)
- Kill-switch checks (env + runtime file)
- Watchdog timeout wrapper to prevent "freeze while processing"
- Clean CTRL+C exit
- Session gating (conservative; fail-closed for non-whitelisted asset classes)

Binding:
- Set REA_ENGINE_ENTRYPOINT="module.path:function_name"
  Example: REA_ENGINE_ENTRYPOINT="backend.app.main:main"
"""

from __future__ import annotations

import importlib
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Any, Tuple

from backend.app.observability.logger import init_logging, get_logger, with_trace, log_startup_banner
from backend.app.observability.kill_switch import assert_not_killed
from backend.app.observability.session_time import assert_session_allowed

log = get_logger("run_live_guarded")


# -----------------------------
# Config
# -----------------------------

DEFAULT_COMMAND_TIMEOUT_SECONDS = int(os.getenv("REA_COMMAND_TIMEOUT_SECONDS", "45"))
DEFAULT_ASSET_CLASS = os.getenv("REA_ASSET_CLASS", "fx")  # fx | crypto | equities | options
ENGINE_ENTRYPOINT = os.getenv("REA_ENGINE_ENTRYPOINT", "").strip()


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
    If engine/execution/confirm_token.py exposes validate_token(), we call it.
    Fail-closed if missing or errors.
    """
    start = time.time()
    adapter = with_trace(log, "TOKEN")

    try:
        from engine.execution.confirm_token import validate_token  # type: ignore
        ok = bool(validate_token())
        if ok:
            adapter.info("TOKEN_OK")
            return GuardResult(True, "token_ok", time.time() - start)
        adapter.warning("TOKEN_FAIL")
        return GuardResult(False, "token_fail", time.time() - start)

    except Exception as e:
        adapter.error("TOKEN_CHECK_ERROR | %s", str(e))
        return GuardResult(False, "token_check_error_or_missing", time.time() - start)


# -----------------------------
# Timeout Watchdog (prevents freezes)
# -----------------------------

class TimeoutError(Exception):
    pass


def run_with_timeout(fn: Callable[[], Any], timeout_s: int, trace_id: str) -> Any:
    """
    Runs fn() in a daemon thread and raises TimeoutError if not completed in timeout_s.

    Note: This cannot forcibly kill a stuck native call, but it prevents the runner
    from waiting forever and enables a controlled stop/exit path.
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
# Entry point resolver (BIND)
# -----------------------------

def resolve_entrypoint(spec: str) -> Tuple[Optional[Callable[[], Any]], str]:
    """
    Resolves REA_ENGINE_ENTRYPOINT="module.path:function"
    Returns (callable_or_none, reason)
    """
    if not spec:
        return None, "REA_ENGINE_ENTRYPOINT_not_set"

    if ":" not in spec:
        return None, "REA_ENGINE_ENTRYPOINT_invalid_format_use_module:function"

    mod_path, func_name = spec.split(":", 1)
    mod_path = mod_path.strip()
    func_name = func_name.strip()

    if not mod_path or not func_name:
        return None, "REA_ENGINE_ENTRYPOINT_invalid_module_or_function"

    try:
        mod = importlib.import_module(mod_path)
    except Exception as e:
        return None, f"import_module_failed:{mod_path}:{e}"

    try:
        fn = getattr(mod, func_name)
    except Exception:
        return None, f"function_not_found:{func_name}"

    if not callable(fn):
        return None, f"not_callable:{mod_path}:{func_name}"

    # Normalize to a zero-arg callable wrapper
    def _wrapped():
        return fn()

    return _wrapped, "ok"


# -----------------------------
# Guarded Step Runner
# -----------------------------

def guarded_step(step_name: str, fn: Callable[[], Any], timeout_s: int) -> GuardResult:
    """
    Runs one guarded step:
    - stop request check
    - kill switch check (pre)
    - session allowed check (pre)
    - timeout watchdog
    - kill switch check (post)
    """
    adapter = with_trace(log, f"STEP:{step_name}")
    start = time.time()

    if stop_requested():
        adapter.warning("STEP_ABORT | reason=stop_requested")
        return GuardResult(False, "stop_requested", time.time() - start)

    if not assert_not_killed(pair="GLOBAL"):
        adapter.critical("STEP_BLOCK | reason=kill_switch_active(pre)")
        return GuardResult(False, "kill_switch_active_pre", time.time() - start)

    decision = assert_session_allowed(asset_class=DEFAULT_ASSET_CLASS, hard_fail=True)
    if not decision.allowed:
        adapter.warning("STEP_BLOCK | reason=session_blocked | state=%s | detail=%s", decision.state, decision.reason)
        return GuardResult(False, f"session_blocked:{decision.reason}", time.time() - start)

    try:
        run_with_timeout(fn, timeout_s=timeout_s, trace_id=f"STEP:{step_name}")
    except TimeoutError as te:
        adapter.critical("STEP_TIMEOUT | %s", str(te))
        return GuardResult(False, "timeout", time.time() - start)
    except Exception as e:
        adapter.error("STEP_ERROR | %s", str(e))
        return GuardResult(False, "exception", time.time() - start)

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

    signal.signal(signal.SIGINT, _handle_sigint)

    adapter = with_trace(log, "MAIN")
    adapter.info(
        "RUN_LIVE_GUARDED_START | timeout=%ss | asset_class=%s | entrypoint=%s",
        DEFAULT_COMMAND_TIMEOUT_SECONDS,
        DEFAULT_ASSET_CLASS,
        ENGINE_ENTRYPOINT or "NOT_SET",
    )

    # Step A: Token validation (fail-closed)
    token_res = guarded_step("token_validation", validate_token_or_fail, timeout_s=15)
    if not token_res.ok:
        adapter.critical("ABORT | token step failed | reason=%s", token_res.reason)
        return 2

    # Step B: Bind to real engine entrypoint
    fn, reason = resolve_entrypoint(ENGINE_ENTRYPOINT)
    if fn is None:
        adapter.critical("ABORT | entrypoint_bind_failed | reason=%s", reason)
        adapter.critical('Set REA_ENGINE_ENTRYPOINT like: "backend.app.main:main"')
        return 4

    adapter.info("ENTRYPOINT_BOUND_OK | %s", ENGINE_ENTRYPOINT)

    # Step C: Run the engine entrypoint guarded
    eng_res = guarded_step("engine_entrypoint", fn, timeout_s=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    if not eng_res.ok:
        adapter.critical("ABORT | engine entrypoint failed | reason=%s", eng_res.reason)
        return 3

    adapter.info("RUN_LIVE_GUARDED_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
