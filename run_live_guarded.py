"""
Authoritative guarded startup wrapper for REA Capital Trading Engine.

Key invariants:
- FAIL-CLOSED by default
- LIVE mode requires explicit confirmation + session gate module present
- TEST mode may run headless paper loop
- TEST + HEADLESS may BYPASS missing session gate module (paper-only),
  but will log a loud warning so we can wire the real session gate later.

This preserves safety while unblocking Phase 1 paper validation.
"""

from __future__ import annotations

import os
import importlib
import uuid
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


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip() in ("1", "true", "TRUE", "yes", "YES", "on", "ON")


def _coerce_gate_result(res: Any) -> Tuple[bool, str]:
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

    allowed = getattr(res, "allowed", getattr(res, "ok", False))
    reason = getattr(res, "reason", "ok" if allowed else "blocked")
    return bool(allowed), str(reason)


def _print_gate(label: str, allowed: bool, reason: str) -> None:
    print(f"{label:<12} | allowed={allowed} | reason={reason}")


# -------------------------------------------------------------------
# gates (best-effort imports; LIVE must be strict)
# -------------------------------------------------------------------

def session_gate_check(mode: str, headless: bool) -> Tuple[bool, str]:
    """
    LIVE: strict. Missing module => BLOCK.
    TEST+HEADLESS: allow bypass if module missing (paper-only), with warning.
    """
    # Candidate module paths (adjust later when we find the real one)
    mod = (
        _safe_import("engine.security.session_gate")
        or _safe_import("engine.auth.session_gate")
        or _safe_import("backend.app.session_gate")
        or _safe_import("backend.app.auth_gate")
        or _safe_import("engine.auth.auth_gate")
    )

    if not mod:
        if mode != "LIVE" and headless:
            return True, "BYPASS_TEST_HEADLESS_SESSION_GATE_MODULE_MISSING"
        return False, "session_gate_module_missing"

    fn = (
        getattr(mod, "check_session_gate", None)
        or getattr(mod, "session_gate_check", None)
        or getattr(mod, "check", None)
    )

    if not callable(fn):
        if mode != "LIVE" and headless:
            return True, "BYPASS_TEST_HEADLESS_SESSION_GATE_FN_MISSING"
        return False, "session_gate_fn_missing"

    try:
        res = fn()
        return _coerce_gate_result(res)
    except Exception as e:
        if mode != "LIVE" and headless:
            return True, f"BYPASS_TEST_HEADLESS_SESSION_GATE_EXCEPTION:{type(e).__name__}"
        return False, f"session_gate_exception:{type(e).__name__}:{e}"


def exec_gate_check() -> Tuple[bool, str]:
    """
    Execution gate: composite allow/block.
    Always strict (TEST and LIVE).
    Missing module => BLOCK (we don't paper-trade blind).
    """
    mod = (
        _safe_import("engine.guards.exec_gate")
        or _safe_import("engine.guards.execution_gate")
        or _safe_import("engine.security.execution_gate")
    )
    if not mod:
        return False, "exec_gate_module_missing"

    fn = (
        getattr(mod, "check_exec_gate", None)
        or getattr(mod, "exec_gate_check", None)
        or getattr(mod, "check", None)
    )
    if not callable(fn):
        return False, "exec_gate_fn_missing"

    try:
        res = fn()
        return _coerce_gate_result(res)
    except Exception as e:
        return False, f"exec_gate_exception:{type(e).__name__}:{e}"


# -------------------------------------------------------------------
# LIVE confirmations (strict)
# -------------------------------------------------------------------

def _live_rate_limit_check() -> Tuple[bool, str]:
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

    mode = os.getenv("REA_ENGINE_MODE", "TEST").upper().strip()
    headless = _env_flag("HEADLESS_DEV_MODE", "0")
    print(f"MODE         | {mode}")
    print(f"HEADLESS     | {int(headless)}")

    # 1) Session gate (mode-aware)
    s_ok, s_reason = session_gate_check(mode=mode, headless=headless)
    _print_gate("SESSION_GATE", s_ok, s_reason)
    if not s_ok:
        _fail(f"FATAL | SESSION_GATE_BLOCK | {s_reason}", 1)

    # Loud warning when we bypass session gate in TEST headless
    if "BYPASS_TEST_HEADLESS" in s_reason:
        print("WARNING      | Session gate bypassed for TEST+HEADLESS only.")
        print("WARNING      | LIVE mode will still fail-closed until session gate module is wired.")

    # 2) Exec gate (always strict)
    e_ok, e_reason = exec_gate_check()
    _print_gate("EXEC_GATE", e_ok, e_reason)
    if not e_ok:
        _fail(f"FATAL | EXEC_GATE_BLOCK | {e_reason}", 1)

    # 3) TEST / PAPER path
    if mode != "LIVE":
        if not headless:
            print("SAFE EXIT    | TEST mode: HEADLESS_DEV_MODE=0; refusing to enter UI/login.")
            return

        # Hard safety: never allow live broker in TEST path.
        os.environ["REA_LIVE_BROKER_OK"] = "0"
        os.environ["LIVE_TRADING"] = "0"

        print("TEST ENTRY   | Entering headless guarded engine (paper/test).")
        _run_headless_guarded_entry()
        return

    # 4) LIVE path (strict confirmations)
    rl_ok, rl_reason = _live_rate_limit_check()
    print(f"RATE_LIMIT   | ok={rl_ok} | reason={rl_reason}")
    if not rl_ok:
        _fail(f"FATAL | RATE_LIMIT_BLOCK | {rl_reason}", 1)

    su = _load_superuser_profile_default()
    print(f"SUPERUSER    | ok={bool(su.get('ok'))} | reason={su.get('reason', 'ok')}")

    if not _env_flag("CONFIRM_LIVE", "0"):
        _fail("FATAL | LIVE_CONFIRM_REQUIRED | set CONFIRM_LIVE=1 to proceed", 1)

    os.environ["REA_LIVE_BROKER_OK"] = "1"
    os.environ["LIVE_TRADING"] = "1"

    print("LIVE ENTRY   | confirmed; entering live guarded engine.")
    _run_live_guarded_engine()


if __name__ == "__main__":
    main()
