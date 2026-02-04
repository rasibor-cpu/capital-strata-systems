"""
Authoritative guarded startup wrapper for REA Capital Trading Engine.

Responsibilities:
- Fail-closed startup
- Ensure ENGINE_RUN_ID exists
- Enforce LIVE/TEST toggle (fail-closed)
- Block on authentication gate
- Bind audit context BEFORE engine entrypoint
- Provide kill-switch visibility (wrapper prints status)

This file is intentionally defensive: it tolerates mixed return-types from gates
(dict OR tuple) and will not crash the wrapper on status printing.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any, Dict, Tuple


def _utc_now_iso() -> str:
    # Keep simple; engine has its own richer time utilities
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v


def _ensure_engine_run_id() -> str:
    run_id = _env("ENGINE_RUN_ID")
    if not run_id:
        run_id = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = run_id
    return run_id


def _normalize_gate_result(x: Any) -> Dict[str, Any]:
    """
    Gate results in this repo have appeared as dicts and (decision, reason) tuples.
    Normalize into {decision, reason, raw}.
    """
    if isinstance(x, dict):
        return {
            "decision": x.get("decision"),
            "reason": x.get("reason"),
            "raw": x,
        }
    if isinstance(x, tuple) and len(x) >= 1:
        decision = x[0]
        reason = x[1] if len(x) > 1 else None
        return {"decision": decision, "reason": reason, "raw": x}
    return {"decision": None, "reason": "unrecognized_gate_result_type", "raw": x}


def _print_banner(engine_run_id: str) -> None:
    print("===================================================")
    print("REA Capital Trading Engine — Guarded Startup Wrapper")
    print(f"UTC_START_TIME={_utc_now_iso()}")
    print(f"ENGINE_RUN_ID={engine_run_id}")
    print(f"REA_ENGINE_MODE={_env('REA_ENGINE_MODE','(not set)')}")
    print(f"REA_ENGINE_ENTRYPOINT={_env('REA_ENGINE_ENTRYPOINT','(not set)')}")
    print("===================================================")


def _require_entrypoint() -> Tuple[str, str]:
    """
    Entry-point must be set like: engine.run_engine:main
    """
    ep = _env("REA_ENGINE_ENTRYPOINT")
    if not ep or ":" not in ep:
        raise RuntimeError('REA_ENGINE_ENTRYPOINT not set. Set like: "engine.run_engine:main"')
    mod, fn = ep.split(":", 1)
    mod = mod.strip()
    fn = fn.strip()
    if not mod or not fn:
        raise RuntimeError('REA_ENGINE_ENTRYPOINT invalid. Set like: "engine.run_engine:main"')
    return mod, fn


def _import_callable(mod_name: str, fn_name: str):
    import importlib

    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name, None)
    if fn is None or not callable(fn):
        raise RuntimeError(f"Entry callable not found: {mod_name}:{fn_name}")
    return fn


def _require_live_allowed() -> None:
    """
    Fail-closed LIVE/TEST enforcement.
    Your existing repo already has backend/app/security/live_toggle.py.
    """
    mode = (_env("REA_ENGINE_MODE", "TEST") or "TEST").strip().upper()

    try:
        from backend.app.security.live_toggle import require_live_allowed  # type: ignore
    except Exception:
        # Fail-closed: if the toggle module is missing, we refuse LIVE and allow TEST only
        if mode != "TEST":
            raise RuntimeError("LIVE_TOGGLE_MISSING_FAIL_CLOSED")
        return

    # Delegate to existing policy
    require_live_allowed(mode=mode)


def _await_login() -> Dict[str, Any]:
    """
    Authentication gate — fail closed.
    Must return dict with at least: user_id, role, unit_code, home_branch, current_branch
    """
    from backend.app.security.auth_gate import await_login_ready_state  # type: ignore

    auth_ctx = await_login_ready_state()
    if not isinstance(auth_ctx, dict) or "user_id" not in auth_ctx:
        raise RuntimeError("AUTH_CONTEXT_INVALID_FAIL_CLOSED")
    return auth_ctx


def _bind_audit_context(auth_ctx: Dict[str, Any]) -> None:
    """
    Bind audit context BEFORE engine entrypoint.
    This repo already has backend/app/observability/audit_context.py.
    """
    try:
        from backend.app.observability.audit_context import set_audit_user  # type: ignore
    except Exception:
        # If missing, fail closed — you explicitly require traceable user_id on logs
        raise RuntimeError("AUDIT_CONTEXT_MISSING_FAIL_CLOSED")

    set_audit_user(
        user_id=auth_ctx.get("user_id"),
        role=auth_ctx.get("role"),
        unit_code=auth_ctx.get("unit_code"),
        home_branch=auth_ctx.get("home_branch"),
        current_branch=auth_ctx.get("current_branch"),
    )


def _show_status() -> None:
    """
    Print a concise status line for the major gates.
    Must never crash.
    """
    def safe_gate(name: str, fn):
        try:
            raw = fn()
            norm = _normalize_gate_result(raw)
            decision = norm.get("decision")
            reason = norm.get("reason")
            print(f"{name:<16} | decision={decision} | reason={reason}")
        except Exception as e:
            print(f"{name:<16} | decision=ERROR | reason={type(e).__name__}:{e}")

    # These are optional; wrapper should not die if one is absent
    def exec_gate():
        from engine.execution.execution_gate import check_execution_gate  # type: ignore
        return check_execution_gate()

    def session_gate():
        from backend.app.observability.session_time import session_allow_state  # type: ignore
        return session_allow_state()

    safe_gate("SESSION_GATE", session_gate)
    safe_gate("EXEC_GATE", exec_gate)


def main() -> int:
    engine_run_id = _ensure_engine_run_id()
    _print_banner(engine_run_id)

    # 1) Live/TEST toggle (fail-closed)
    _require_live_allowed()

    # 2) Show gate status (must never crash)
    _show_status()

    # 3) Auth gate (fail-closed)
    auth_ctx = _await_login()
    print(f"AUTH_OK | user_id={auth_ctx.get('user_id')} | role={auth_ctx.get('role')} | unit={auth_ctx.get('unit_code')}")

    # 4) Bind audit context (fail-closed)
    _bind_audit_context(auth_ctx)
    print("AUDIT_CONTEXT_OK")

    # 5) Load engine entrypoint and run
    mod, fn = _require_entrypoint()
    entry = _import_callable(mod, fn)
    print(f"ENTRYPOINT_OK | {mod}:{fn}")

    try:
        # If your engine main accepts kwargs later, we can add them.
        entry()
        print("RUN_OK")
        return 0
    except KeyboardInterrupt:
        print("RUN_ABORT | KeyboardInterrupt")
        return 130
    except Exception as e:
        print(f"RUN_ABORT | {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
