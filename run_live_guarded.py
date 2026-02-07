"""
Authoritative guarded startup wrapper for REA Capital Trading Engine.

Responsibilities:
- Fail-closed startup (default BLOCK)
- Ensure ENGINE_RUN_ID exists
- Evaluate session gate and execution gate BEFORE engine entry
- Enforce LIVE / TEST mode execution rules
- In TEST mode: allow headless (paper) engine entry when HEADLESS_DEV_MODE=1
- In LIVE mode: require explicit confirmation checks (rate-limit / superuser / etc)
"""

from __future__ import annotations

import os
import sys
import uuid
import importlib
from typing import Any, Optional, Tuple


# -------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------

def ensure_engine_run_id() -> str:
    run_id = os.getenv("ENGINE_RUN_ID")
    if not run_id:
        run_id = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = run_id
    return run_id


def _utc_now_iso() -> str:
    # Keep it simple; do not hard-depend on dateutil.
    # Use UTC offset display if available.
    try:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    except Exception:
        return "UTC_NOW_UNAVAILABLE"


def _fail(msg: str, exit_code: int = 1) -> None:
    print(msg)
    raise SystemExit(exit_code)


def _safe_import(modname: str):
    try:
        return importlib.import_module(modname)
    except Exception:
        return None


def _coerce_gate_result(res: Any) -> Tuple[bool, str]:
    """
    Accepts gate results as:
    - bool
    - tuple(bool, reason)
    - dict with keys: allowed/ok, reason
    - object with attributes: allowed/ok, reason
    """
    if isinstance(res, bool):
        return res, "ok" if res else "blocked"

    if isinstance(res, tuple) and len(res) >= 1:
        allowed = bool(res[0])
        reason = str(res[1]) if len(res) > 1 else ("ok" if allowed else "blocked")
        return allowed, reason

    if isinstance(res, dict):
        allowed = res.get("allowed", res.get("ok", False))
        reason = res.get("reason", "ok" if allowed else "blocked")
        return bool(allowed), str(reason)

    # object-like
    allowed = getattr(res, "allowed", getattr(res, "ok", False))
    reason = getattr(res, "reason", "ok" if allowed else "blocked")
    return bool(allowed), str(reason)


def _print_gate(label: str, allowed: bool, reason: str) -> None:
    print(f"{label:<12} | allowed={allowed} | reason={reason}")


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip() in ("1", "true", "TRUE", "yes", "YES", "on", "ON")


# -------------------------------------------------------------------
# guarded checks (best-effort imports; fail-closed if missing)
# -------------------------------------------------------------------

def session_gate_check() -> Tuple[bool, str]:
    """
    Session gate: authentication / session validation.
    Fail-closed if module not found or exceptions occur.
    """
    mod = _safe_import("engine.security.session_gate") or _safe_import("engine.auth.session_gate")
    if not mod:
        # If your repo uses a different path, update it once and keep it stable.
        return False, "session_gate_module_missing"

    fn = getattr(mod, "check_session_gate", None) or getattr(mod, "session_gate_check", None) or getattr(mod, "check", None)
    if not callable(fn):
        return False, "session_gate_fn_missing"

    try:
        res = fn()
        return _coerce_gate_result(res)
    except Exception as e:
        return False, f"session_gate_exception:{type(e).__name__}:{e}"


def exec_gate_check() -> Tuple[bool, str]:
    """
    Execution gate: risk/regime/vol/liquidity/etc composite allow/block.
    Fail-closed if module not found or exceptions occur.
    """
    mod = _safe_import("engine.guards.exec_gate") or _safe_import("engine.guards.execution_gate") or _safe_import("engine.security.execution_gate")
    if not mod:
        return False, "exec_gate_module_missing"

    fn = getattr(mod, "check_exec_gate", None) or getattr(mod, "exec_gate_check", None) or getattr(mod, "check", None)
    if not callable(fn):
        return False, "exec_gate_fn_missing"

    try:
        res = fn()
        return _coerce_gate_result(res)
    except Exception as e:
        return False, f"exec_gate_exception:{type(e).__name__}:{e}"


# -------------------------------------------------------------------
# live-specific optional confirmations (fail-closed if checks missing)
# -------------------------------------------------------------------

def _live_rate_limit_check() -> Tuple[bool, str]:
    """
    Optional LIVE confirmation: rate-limit check / live sanity.
    If the module/function is missing, we fail-closed (LIVE is high-stakes).
    """
    mod = _safe_import("engine.live.rate_limit") or _safe_import("engine.live.live_checks")
    if not mod:
        return False, "live_rate_limit_module_missing"

    fn = getattr(mod, "rate_limit_check", None) or getattr(mod, "confirm_live_rate_limit", None) or getattr(mod, "check_rate_limit", None)
    if not callable(fn):
        return False, "live_rate_limit_fn_missing"

    try:
        res = fn()
        return _coerce_gate_result(res)
    except Exception as e:
        return False, f"live_rate_limit_exception:{type(e).__name__}:{e}"


def _load_superuser_profile_default() -> dict:
    """
    Optional: superuser profile load.
    This MUST NOT enable anything by itself—only informs logging.
    """
    mod = _safe_import("engine.security.superuser") or _safe_import("engine.auth.superuser")
    if not mod:
        return {"ok": False, "reason": "superuser_module_missing"}

    fn = getattr(mod, "load_superuser_profile_default", None) or getattr(mod, "load_default", None)
    if not callable(fn):
        return {"ok": False, "reason": "superuser_fn_missing"}

    try:
        out = fn()
        if isinstance(out, dict):
            out.setdefault("ok", True)
            return out
        return {"ok": True, "value": out}
    except Exception as e:
        return {"ok": False, "reason": f"superuser_exception:{type(e).__name__}:{e}"}


# -------------------------------------------------------------------
# entrypoints
# -------------------------------------------------------------------

def _run_headless_guarded_entry() -> None:
    """
    Preferred headless entrypoint for TEST/PAPER runs.
    """
    # Try most canonical first
    candidates = [
        ("backend.app.headless_guarded_entry", "main"),
        ("backend.app.headless_guarded_entry", "run"),
        ("backend.app.headless_guarded_entry", "entry"),
        ("backend.app.main", "main"),
    ]

    last_err: Optional[str] = None

    for modname, fnname in candidates:
        mod = _safe_import(modname)
        if not mod:
            continue
        fn = getattr(mod, fnname, None)
        if callable(fn):
            try:
                fn()
                return
            except SystemExit:
                raise
            except Exception as e:
                last_err = f"{modname}.{fnname} -> {type(e).__name__}: {e}"

    _fail(f"FATAL | HEADLESS_ENTRY_NOT_FOUND | {last_err or 'no_candidate_matched'}", 1)


def _run_live_guarded_engine() -> None:
    """
    LIVE guarded engine entry (must exist and must be safe by design).
    """
    candidates = [
        ("backend.run_live_guarded", "main"),
        ("backend.run_live_guarded", "run"),
        ("backend.app.main", "main"),
    ]

    last_err: Optional[str] = None
    for modname, fnname in candidates:
        mod = _safe_import(modname)
        if not mod:
            continue
        fn = getattr(mod, fnname, None)
        if callable(fn):
            try:
                fn()
                return
            except SystemExit:
                raise
            except Exception as e:
                last_err = f"{modname}.{fnname} -> {type(e).__name__}: {e}"

    _fail(f"FATAL | LIVE_ENTRY_NOT_FOUND | {last_err or 'no_candidate_matched'}", 1)


# -------------------------------------------------------------------
# main
# -------------------------------------------------------------------

def main() -> None:
    print("=== REA GUARDED STARTUP (FAIL-CLOSED) ===")
    print(f"UTC_NOW={_utc_now_iso()}")
    print(f"ENGINE_RUN_ID={ensure_engine_run_id()}")

    # 1) Session gate
    s_ok, s_reason = session_gate_check()
    _print_gate("SESSION_GATE", s_ok, s_reason)
    if not s_ok:
        _fail(f"FATAL | SESSION_GATE_BLOCK | {s_reason}", 1)

    # 2) Exec gate
    e_ok, e_reason = exec_gate_check()
    _print_gate("EXEC_GATE", e_ok, e_reason)
    if not e_ok:
        _fail(f"FATAL | EXEC_GATE_BLOCK | {e_reason}", 1)

    # 3) Mode selection
    mode = os.getenv("REA_ENGINE_MODE", "TEST").upper().strip()
    print(f"MODE         | {mode}")

    # Always default to safe.
    if mode != "LIVE":
        # TEST/PAPER path
        headless = _env_flag("HEADLESS_DEV_MODE", "0")
        if not headless:
            print("SAFE EXIT    | TEST mode: HEADLESS_DEV_MODE=0; refusing to enter UI/login.")
            return

        # Additional hard safety: do not allow accidental live broker use in TEST.
        os.environ["REA_LIVE_BROKER_OK"] = "0"
        os.environ["LIVE_TRADING"] = "0"

        print("TEST ENTRY   | HEADLESS_DEV_MODE=1; entering headless guarded engine (paper/test).")
        _run_headless_guarded_entry()
        return

    # 4) LIVE-specific confirmations (fail-closed)
    rl_ok, rl_reason = _live_rate_limit_check()
    print(f"RATE_LIMIT   | ok={rl_ok} | reason={rl_reason}")
    if not rl_ok:
        _fail(f"FATAL | RATE_LIMIT_BLOCK | {rl_reason}", 1)

    su = _load_superuser_profile_default()
    print(f"SUPERUSER    | ok={bool(su.get('ok'))} | reason={su.get('reason', 'ok')}")

    # Explicit allow flag required for LIVE (prevents accidental LIVE start)
    if not _env_flag("CONFIRM_LIVE", "0"):
        _fail("FATAL | LIVE_CONFIRM_REQUIRED | set CONFIRM_LIVE=1 to proceed", 1)

    # LIVE broker allowed only when explicitly confirmed
    os.environ["REA_LIVE_BROKER_OK"] = "1"
    os.environ["LIVE_TRADING"] = "1"

    print("LIVE ENTRY   | confirmed; entering live guarded engine.")
    _run_live_guarded_engine()


if __name__ == "__main__":
    main()
