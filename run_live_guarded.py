"""
Authoritative GUARDED startup wrapper for REA Capital Trading Engine.

ENFORCED INVARIANTS
-------------------
1. FAIL-CLOSED: Any gate ERROR or exception => immediate STOP
2. NO LOGIN unless ALL gates explicitly ALLOW
3. SESSION & EXEC gates run BEFORE auth
4. LIVE execution requires explicit LIVE mode
5. Defensive against dict / object / tuple / None / exception
"""

from __future__ import annotations

import os
import sys
import uuid
import importlib
from typing import Any


# ===============================================================
# Helpers
# ===============================================================

def ensure_engine_run_id() -> str:
    run_id = os.getenv("ENGINE_RUN_ID") or os.getenv("REA_ENGINE_RUN_ID")
    if not run_id:
        run_id = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = run_id
    return run_id


def normalize_decision(decision: Any) -> dict:
    """
    Normalize ANY gate decision into:
    {
        allowed: bool,
        reason: str,
        error: bool
    }
    """
    if decision is None:
        return {"allowed": False, "reason": "no_decision", "error": True}

    if isinstance(decision, dict):
        return {
            "allowed": bool(decision.get("allowed", False)),
            "reason": str(decision.get("reason", "unknown")),
            "error": decision.get("decision") == "ERROR",
        }

    if hasattr(decision, "__dict__"):
        return {
            "allowed": bool(getattr(decision, "allowed", False)),
            "reason": str(getattr(decision, "reason", "unknown")),
            "error": getattr(decision, "decision", None) == "ERROR",
        }

    if isinstance(decision, tuple):
        allowed = bool(decision[0]) if len(decision) > 0 else False
        reason = str(decision[1]) if len(decision) > 1 else "tuple_decision"
        return {"allowed": allowed, "reason": reason, "error": False}

    return {
        "allowed": False,
        "reason": f"unsupported_decision_type:{type(decision)}",
        "error": True,
    }


def hard_stop(label: str, detail: str) -> None:
    print(f"FATAL | {label} | {detail}")
    sys.exit(1)


def show_gate(label: str, d: dict) -> None:
    print(
        f"[{label}] "
        f"allowed={d['allowed']} "
        f"| reason={d['reason']} "
        f"| error={d['error']}"
    )


def require_live_mode() -> None:
    mode = os.getenv("REA_ENGINE_MODE", "TEST").upper()
    if mode != "LIVE":
        hard_stop("MODE_BLOCK", "LIVE execution requested in TEST mode")


# ===============================================================
# Main
# ===============================================================

def main() -> None:
    print("=== REA GUARDED STARTUP ===")

    # -----------------------------------------------------------
    # 0) Audit context
    # -----------------------------------------------------------
    run_id = ensure_engine_run_id()
    print(f"ENGINE_RUN_ID={run_id}")

    # -----------------------------------------------------------
    # 1) SESSION GATE (NO AUTH HERE)
    # -----------------------------------------------------------
    try:
        from backend.app.observability.session_time import session_allow_state
        session_decision = session_allow_state()
    except Exception as e:
        hard_stop("SESSION_GATE_EXCEPTION", str(e))

    s = normalize_decision(session_decision)
    show_gate("SESSION_GATE", s)

    if s["error"] or not s["allowed"]:
        hard_stop("SESSION_GATE_BLOCK", s["reason"])

    # -----------------------------------------------------------
    # 2) EXECUTION GATE (NO AUTH HERE)
    # -----------------------------------------------------------
    try:
        from engine.execution.execution_gate import execution_gate_check
        exec_decision = execution_gate_check()
    except Exception as e:
        hard_stop("EXEC_GATE_EXCEPTION", str(e))

    e = normalize_decision(exec_decision)
    show_gate("EXEC_GATE", e)

    if e["error"] or not e["allowed"]:
        hard_stop("EXEC_GATE_BLOCK", e["reason"])

    # -----------------------------------------------------------
    # 3) AUTH GATE (ONLY AFTER ALL GATES PASS)
    # -----------------------------------------------------------
    try:
        from backend.app.security.auth_gate import await_login_ready_state
        auth_ctx, unit_ctx = await_login_ready_state()
    except Exception as e:
        hard_stop("AUTH_FAILURE", str(e))

    print(
        f"AUTH_OK | user={auth_ctx.user_id} "
        f"| role={auth_ctx.role} "
        f"| unit={auth_ctx.unit_code}"
    )

    # -----------------------------------------------------------
    # 4) LIVE MODE ENFORCEMENT
    # -----------------------------------------------------------
    require_live_mode()

    # -----------------------------------------------------------
    # 5) ENGINE ENTRYPOINT
    # -----------------------------------------------------------
    entry = os.getenv("REA_ENGINE_ENTRYPOINT")
    if not entry:
        hard_stop("ENTRYPOINT_MISSING", "REA_ENGINE_ENTRYPOINT not set")

    module_name, func_name = entry.split(":")
    print(f"ENTRYPOINT={module_name}:{func_name}")

    try:
        mod = importlib.import_module(module_name)
        fn = getattr(mod, func_name)
    except Exception as e:
        hard_stop("ENTRYPOINT_LOAD_FAIL", str(e))

    print("=== ENGINE START ===")
    fn()


# ===============================================================
# Bootstrap
# ===============================================================

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        hard_stop("UNHANDLED_EXCEPTION", str(e))
