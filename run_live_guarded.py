"""
Authoritative guarded startup wrapper for REA Capital Trading Engine.

Contract (FAIL-CLOSED, ALWAYS):
- If SESSION_GATE or EXEC_GATE errors -> HARD STOP (fail-closed) -> NO login prompt.
- Login/auth gate runs ONLY after gates are healthy (import + callable discovery OK).
- Execution decisions may be dict/object/tuple -> normalize safely.
- LIVE vs TEST enforcement: LIVE requires explicit allow + policy + armed state (where available).
- Wrapper must be resilient to function renames (getattr fallbacks).
"""

from __future__ import annotations

import importlib
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple


# -------------------------
# primitives / helpers
# -------------------------

def _utc_now_iso() -> str:
    # timezone-safe (avoid datetime.utcnow deprecation)
    try:
        import datetime as _dt
        return _dt.datetime.now(_dt.timezone.utc).isoformat()
    except Exception:
        return "utc_now_unavailable"


def ensure_engine_run_id() -> str:
    run_id = os.getenv("ENGINE_RUN_ID") or os.getenv("REA_ENGINE_RUN_ID") or os.getenv("REA_RUN_ID")
    if not run_id:
        run_id = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = run_id
    return run_id


def _fail(msg: str, code: int = 1) -> None:
    print(msg)
    raise SystemExit(code)


def safe_import(module_name: str) -> Tuple[bool, Optional[Any], Optional[str]]:
    try:
        mod = importlib.import_module(module_name)
        return True, mod, None
    except Exception as e:
        return False, None, f"{type(e).__name__}: {e}"


def pick_callable(mod: Any, names: list[str]) -> Optional[Callable[..., Any]]:
    for n in names:
        fn = getattr(mod, n, None)
        if callable(fn):
            return fn
    return None


def normalize_decision(decision: Any) -> dict:
    """
    Normalize ANY decision shape into a dict with:
      - allowed: bool
      - reason: str
      - raw: original (for debugging)
    """
    if decision is None:
        return {"allowed": False, "reason": "no_decision_returned", "raw": None}

    if isinstance(decision, dict):
        return {
            "allowed": bool(decision.get("allowed", decision.get("ok", False))),
            "reason": str(decision.get("reason", decision.get("error", "unknown"))),
            "raw": decision,
        }

    # dataclass/object with attributes
    if hasattr(decision, "__dict__"):
        return {
            "allowed": bool(getattr(decision, "allowed", getattr(decision, "ok", False))),
            "reason": str(getattr(decision, "reason", getattr(decision, "error", "unknown"))),
            "raw": decision,
        }

    # tuple fallback (allowed, reason, ...)
    if isinstance(decision, tuple):
        allowed = bool(decision[0]) if len(decision) >= 1 else False
        reason = str(decision[1]) if len(decision) >= 2 else "tuple_decision"
        return {"allowed": allowed, "reason": reason, "raw": decision}

    return {"allowed": False, "reason": f"unsupported_decision_type:{type(decision)}", "raw": decision}


def show_gate(label: str, decision: Any) -> dict:
    d = normalize_decision(decision)
    print(f"{label:<12} | allowed={d['allowed']} | reason={d['reason']}")
    return d


def require_live_allowed() -> None:
    """
    Enforce LIVE/TEST mode rule:
    - If REA_ENGINE_MODE != LIVE -> block anything that would proceed past gates.
    """
    mode = os.getenv("REA_ENGINE_MODE", "TEST").upper().strip()
    if mode != "LIVE":
        _fail("FATAL | MODE_BLOCK: REA_ENGINE_MODE is not LIVE (current: %s)" % mode, 2)


# -------------------------
# capability probing (fail-closed)
# -------------------------

@dataclass
class GateCaps:
    ok: bool
    reason: str
    session_gate_fn: Optional[Callable[..., Any]] = None
    exec_gate_fn: Optional[Callable[..., Any]] = None


def probe_gates_fail_closed() -> GateCaps:
    """
    HARD RULE:
      If we cannot import/probe BOTH SESSION and EXEC gates -> STOP immediately.
      This must happen BEFORE any auth/login prompt.
    """

    # SESSION_GATE: backend.app.observability.session_time session_allow_state (or compat names)
    ok_s, mod_s, err_s = safe_import("backend.app.observability.session_time")
    if not ok_s:
        return GateCaps(False, f"SESSION_GATE_EXCEPTION | cannot import session_time | {err_s}")

    session_fn = pick_callable(mod_s, [
        "session_allow_state",
        "get_session_allow_state",
        "session_gate_check",
        "check_session_gate",
    ])
    if not session_fn:
        return GateCaps(False, "SESSION_GATE_EXCEPTION | session allow function not found (expected session_allow_state or compat name)")

    # EXEC_GATE: engine.execution.execution_gate check_execution_gate (or compat names)
    ok_e, mod_e, err_e = safe_import("engine.execution.execution_gate")
    if not ok_e:
        return GateCaps(False, f"EXEC_GATE_EXCEPTION | cannot import engine.execution.execution_gate | {err_e}")

    exec_fn = pick_callable(mod_e, [
        "check_execution_gate",
        "execution_gate_check",
        "check_exec_gate",
        "exec_gate_check",
    ])
    if not exec_fn:
        return GateCaps(False, "EXEC_GATE_EXCEPTION | execution gate function not found (expected check_execution_gate or compat name)")

    return GateCaps(True, "ok", session_gate_fn=session_fn, exec_gate_fn=exec_fn)


# -------------------------
# optional components (non-fatal by design)
# -------------------------

def try_load_live_state() -> Tuple[bool, Optional[Any], str]:
    ok, mod, err = safe_import("engine.execution.live_state")
    if not ok:
        return False, None, f"live_state import fail: {err}"

    get_fn = pick_callable(mod, ["get_live_state", "read_live_state"])
    if not get_fn:
        return False, None, "live_state getter not found"

    try:
        state = get_fn()
        return True, state, "ok"
    except Exception as e:
        return False, None, f"live_state getter failed: {type(e).__name__}: {e}"


def try_rate_limit_check(action: str) -> Tuple[bool, str]:
    """
    Best-effort. If arming_rate_limit exists, use it. If not, allow but do NOT weaken fail-closed.
    """
    ok, mod, err = safe_import("engine.execution.arming_rate_limit")
    if not ok:
        return True, "rate_limit module missing (skipped)"

    fn = pick_callable(mod, [
        "check_rate_limit",
        "rate_limit_ok",
        "assert_rate_limit",
    ])
    if not fn:
        return True, "rate_limit fn missing (skipped)"

    try:
        # expected to return bool or raise
        out = fn(action=action) if "action" in getattr(fn, "__code__", type("x",(object,),{"co_varnames":()})) .co_varnames else fn()
        if isinstance(out, bool) and not out:
            return False, "rate_limited"
        return True, "ok"
    except Exception as e:
        # fail-closed on rate-limit errors
        return False, f"rate_limit_error:{type(e).__name__}:{e}"


def load_superuser_profile_default() -> dict:
    """
    Fail-closed *for live arming*, but this wrapper treats missing profile as:
    - If LIVE is requested later, the arming pipeline must block.
    - For guarded startup, we only report status.
    """
    ok, mod, err = safe_import("config.superuser")
    if not ok:
        return {"ok": False, "reason": f"superuser loader missing: {err}"}

    fn = pick_callable(mod, ["load_superuser", "load_superuser_profile", "load_profile"])
    if not fn:
        return {"ok": False, "reason": "superuser loader fn not found"}

    try:
        profile = fn()
        return {"ok": True, "profile": profile, "reason": "ok"}
    except Exception as e:
        return {"ok": False, "reason": f"superuser load failed: {type(e).__name__}: {e}"}


# -------------------------
# main
# -------------------------

def main() -> None:
    print("=== REA GUARDED STARTUP (FAIL-CLOSED) ===")
    print(f"UTC_NOW={_utc_now_iso()}")
    run_id = ensure_engine_run_id()
    print(f"ENGINE_RUN_ID={run_id}")

    # 0) PROBE GATES FIRST (NO LOGIN IF ERROR)
    caps = probe_gates_fail_closed()
    if not caps.ok:
        _fail(f"FATAL | {caps.reason}", 1)

    # 1) SESSION_GATE check (fail-closed)
    try:
        session_decision = caps.session_gate_fn()  # expected to return decision-like
        d_s = show_gate("SESSION_GATE", session_decision)
        if not d_s["allowed"]:
            _fail("FATAL | SESSION_GATE_BLOCK | " + d_s["reason"], 1)
    except SystemExit:
        raise
    except Exception as e:
        _fail(f"FATAL | SESSION_GATE_EXCEPTION | {type(e).__name__}: {e}", 1)

    # 2) EXEC_GATE check (fail-closed)
    try:
        exec_decision = caps.exec_gate_fn()  # decision-like
        d_e = show_gate("EXEC_GATE", exec_decision)
        if not d_e["allowed"]:
            _fail("FATAL | EXEC_GATE_BLOCK | " + d_e["reason"], 1)
    except SystemExit:
        raise
    except Exception as e:
        _fail(f"FATAL | EXEC_GATE_EXCEPTION | {type(e).__name__}: {e}", 1)

    # 3) If LIVE mode, require it explicitly; otherwise stop here cleanly
    mode = os.getenv("REA_ENGINE_MODE", "TEST").upper().strip()
    print(f"MODE        | {mode}")
    if mode != "LIVE":
        print("SAFE EXIT   | TEST mode: gates OK; refusing to proceed into login/engine.")
        return

    # 4) LIVE-specific optional checks (rate limit, superuser profile, live_state)
    ok_rl, rl_reason = try_rate_limit_check(action="confirm_live")
    print(f"RATE_LIMIT  | ok={ok_rl} | {rl_reason}")
    if not ok_rl:
        _fail("FATAL | RATE_LIMIT_BLOCK | " + rl_reason, 1)

    su = load_superuser_profile_default()
    print(f"SUPERUSER   | ok={su.get('ok')} | {su.get('reason')}")
    if not su.get("ok"):
        _fail("FATAL | SUPERUSER_PROFILE_REQUIRED_FOR_LIVE | " + str(su.get("reason")), 1)

    ok_ls, live_state, ls_reason = try_load_live_state()
    print(f"LIVE_STATE  | ok={ok_ls} | {ls_reason}")
    if ok_ls:
        # do not assume schema; just print safely
        try:
            print(f"LIVE_STATE  | {live_state}")
        except Exception:
            print("LIVE_STATE  | (unprintable)")

    # 5) AUTH gate (BLOCKING) — ONLY after gates OK
    try:
        from backend.app.security.auth_gate import await_login_ready_state
    except Exception as e:
        _fail(f"FATAL | AUTH_GATE_IMPORT_FAIL | {type(e).__name__}: {e}", 1)

    auth_ctx, unit_bundle = await_login_ready_state()
    print(
        f"AUTH_OK     | user_id={getattr(auth_ctx, 'user_id', 'na')} "
        f"| role={getattr(auth_ctx, 'role', 'na')} "
        f"| unit={getattr(auth_ctx, 'unit_code', 'na')} "
        f"| branch={getattr(auth_ctx, 'current_branch', 'na')}"
    )

    # 6) Engine entrypoint
    entry = os.getenv("REA_ENGINE_ENTRYPOINT") or os.getenv("REA_ENGINE_ENTRYPOINT", "")
    if not entry:
        _fail("FATAL | REA_ENGINE_ENTRYPOINT not set (example: engine.run_engine:main)", 1)

    if ":" not in entry:
        _fail("FATAL | REA_ENGINE_ENTRYPOINT invalid (expected module:function)", 1)

    module_name, func_name = entry.split(":", 1)
    print(f"ENTRYPOINT  | {module_name}:{func_name}")

    try:
        mod = importlib.import_module(module_name)
        fn = getattr(mod, func_name)
        if not callable(fn):
            _fail("FATAL | ENTRYPOINT_NOT_CALLABLE", 1)
    except Exception as e:
        _fail(f"FATAL | ENTRYPOINT_IMPORT_FAIL | {type(e).__name__}: {e}", 1)

    print("=== ENGINE START ===")
    fn()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"FATAL | {type(e).__name__}: {e}")
        raise SystemExit(1)
