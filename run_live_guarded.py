"""
Authoritative guarded startup wrapper for REA Capital Trading Engine.

Responsibilities:
- Fail-closed startup
- Ensure ENGINE_RUN_ID exists
- Block on authentication gate
- Bind audit context BEFORE engine entrypoint
- Enforce LIVE / TEST mode execution rules
- Safely display execution gate decisions (object / tuple / dict)
"""

from __future__ import annotations

import os
import sys
import importlib
import uuid
from typing import Any


# -------------------------------------------------------------------
# helpers
# -------------------------------------------------------------------

def ensure_engine_run_id() -> str:
    run_id = os.getenv("ENGINE_RUN_ID") or os.getenv("REA_ENGINE_RUN_ID")
    if not run_id:
        run_id = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = run_id
    return run_id


def normalize_decision(decision: Any) -> dict:
    """
    Normalize ANY execution decision shape into a dict.

    Supported:
    - dict
    - dataclass / object with attributes
    - tuple / namedtuple (best-effort)
    """
    if decision is None:
        return {
            "allowed": False,
            "reason": "no_decision_returned",
        }

    # dict
    if isinstance(decision, dict):
        return {
            "allowed": decision.get("allowed", False),
            "reason": decision.get("reason", "unknown"),
        }

    # object with attributes
    if hasattr(decision, "__dict__"):
        return {
            "allowed": getattr(decision, "allowed", False),
            "reason": getattr(decision, "reason", "unknown"),
        }

    # tuple (fallback)
    if isinstance(decision, tuple):
        allowed = False
        reason = "tuple_decision"

        if len(decision) >= 1:
            allowed = bool(decision[0])
        if len(decision) >= 2:
            reason = str(decision[1])

        return {
            "allowed": allowed,
            "reason": reason,
        }

    # unknown
    return {
        "allowed": False,
        "reason": f"unsupported_decision_type:{type(decision)}",
    }


def show_status(label: str, decision: Any) -> None:
    d = normalize_decision(decision)
    print(
        f"[{label}] EXECUTION_GATE | "
        f"allowed={d['allowed']} | reason={d['reason']}"
    )


def require_live_allowed() -> None:
    """
    Enforce LIVE / TEST mode rules.
    """
    mode = os.getenv("REA_ENGINE_MODE", "TEST").upper()
    if mode != "LIVE":
        raise RuntimeError("EXECUTION_BLOCKED_TEST_MODE")


# -------------------------------------------------------------------
# main
# -------------------------------------------------------------------

def main() -> None:
    print("=== REA GUARDED STARTUP ===")

    # 1) ensure audit run id
    run_id = ensure_engine_run_id()
    print(f"ENGINE_RUN_ID={run_id}")

    # 2) authentication gate (BLOCKING)
    from backend.app.security.auth_gate import await_login_ready_state

    auth_ctx, unit_bundle = await_login_ready_state()
    print(
        f"AUTH_OK | user_id={auth_ctx.user_id} "
        f"| role={auth_ctx.role} "
        f"| unit={auth_ctx.unit_code} "
        f"| branch={auth_ctx.current_branch}"
    )

    # 3) execution router (pre-flight)
    try:
        from engine.execution_router import ExecutionRouter
    except Exception:
        from execution_router import ExecutionRouter  # fallback

    router = ExecutionRouter(
        analysis_only=(os.getenv("REA_ENGINE_MODE", "TEST").upper() != "LIVE")
    )

    decision = router.evaluate(risk_flag=True)
    show_status("PRECHECK", decision)

    d = normalize_decision(decision)
    if not d["allowed"]:
        print("ABORT | execution gate blocked startup")
        sys.exit(1)

    # 4) LIVE mode enforcement
    require_live_allowed()

    # 5) engine entrypoint
    entry = os.getenv("REA_ENGINE_ENTRYPOINT")
    if not entry:
        raise RuntimeError(
            "REA_ENGINE_ENTRYPOINT not set "
            "(example: engine.run_engine:main)"
        )

    module_name, func_name = entry.split(":")
    print(f"ENTRYPOINT | {module_name}:{func_name}")

    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name)

    print("=== ENGINE START ===")
    fn()


# -------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL | {e}")
        sys.exit(1)
