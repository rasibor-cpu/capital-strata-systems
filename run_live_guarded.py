"""
run_live_guarded.py

Authoritative guarded startup wrapper for REA Capital Trading Engine.

Responsibilities:
- Fail-closed startup
- Ensure ENGINE_RUN_ID exists
- Block on authentication gate
- Bind audit context BEFORE engine entrypoint
- Enforce LIVE / TEST mode toggle
- Abort safely on any violation
"""

import os
import sys
import time
import uuid
import importlib
import traceback

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.kill_switch import assert_not_killed
from backend.app.security.auth_gate import await_login_ready_state

log = get_logger("run_live_guarded")


def _ensure_engine_run_id() -> str:
    """
    Guarantee a stable ENGINE_RUN_ID for this process.
    """
    rid = os.getenv("ENGINE_RUN_ID", "").strip()
    if not rid:
        rid = str(uuid.uuid4())
        os.environ["ENGINE_RUN_ID"] = rid
    return rid


def _load_entrypoint(entrypoint: str):
    """
    Resolve entrypoint string: module:function
    """
    if ":" not in entrypoint:
        raise ValueError("Invalid entrypoint format. Use module:function")

    mod_name, fn_name = entrypoint.split(":", 1)
    module = importlib.import_module(mod_name)
    fn = getattr(module, fn_name, None)

    if fn is None:
        raise AttributeError(f"Entrypoint function '{fn_name}' not found in {mod_name}")

    return fn


def main():
    trace = with_trace(log, "STARTUP")

    # =============================
    # Fail-closed kill switch
    # =============================
    if not assert_not_killed(pair="GLOBAL"):
        trace.critical("ABORT | kill_switch_active")
        sys.exit(1)

    engine_run_id = _ensure_engine_run_id()
    mode = os.getenv("REA_ENGINE_MODE", "TEST").upper()
    entrypoint = os.getenv("REA_ENGINE_ENTRYPOINT", "").strip()

    trace.info(
        "RUN_LIVE_GUARDED_START | run_id=%s | mode=%s | entrypoint=%s",
        engine_run_id,
        mode,
        entrypoint or "NOT_SET",
    )

    if not entrypoint:
        trace.critical("ABORT | reason=REA_ENGINE_ENTRYPOINT_not_set")
        sys.exit(1)

    # =============================
    # AUTH GATE (BLOCKING)
    # =============================
    try:
        auth_ctx = await_login_ready_state()
        trace.info(
            "AUTH_OK | user_id=%s | role=%s | unit=%s | branch=%s",
            auth_ctx.user_id,
            auth_ctx.role,
            auth_ctx.unit_code,
            auth_ctx.current_branch,
        )
    except Exception as exc:
        trace.critical("AUTH_ABORT | %s", str(exc))
        sys.exit(1)

    # =============================
    # MODE SAFETY
    # =============================
    if mode == "LIVE":
        trace.warning("ENGINE_MODE=LIVE | additional safeguards enforced")

    # =============================
    # LOAD & RUN ENGINE
    # =============================
    try:
        engine_main = _load_entrypoint(entrypoint)
        trace.info("ENTRYPOINT_BOUND_OK | %s", entrypoint)
        engine_main()
    except Exception as exc:
        trace.critical("ENGINE_ABORT | %s", str(exc))
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
