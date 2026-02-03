"""
run_live_guarded.py

Authoritative guarded launcher for REA Capital Trading Engine.

Execution order (LOCKED):
1. Startup + safety checks
2. Login gate (auth_gate.await_login_ready_state)
   - sets AuditContext
   - binds user permissions
3. Resolve execution entrypoint
4. Execute engine entrypoint

Fail-closed at every step.
"""

from __future__ import annotations

import importlib
import os
import sys
import time

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.engine_run import init_engine_run
from backend.app.observability.kill_switch import assert_not_killed
from backend.app.security.auth_gate import await_login_ready_state

log = get_logger("run_live_guarded")


def _resolve_entrypoint(entrypoint: str):
    """
    Resolve entrypoint string of form: module.path:function_name
    """
    if ":" not in entrypoint:
        raise ValueError("Invalid entrypoint format. Expected module:function")

    module_path, func_name = entrypoint.split(":", 1)
    module = importlib.import_module(module_path)
    fn = getattr(module, func_name, None)

    if fn is None or not callable(fn):
        raise RuntimeError(f"Entrypoint function not found: {entrypoint}")

    return fn


def main() -> None:
    adapter = with_trace(log, "STARTUP")

    # -------------------------------------------------
    # 1) Engine run + kill switch
    # -------------------------------------------------
    init_engine_run()

    if not assert_not_killed(pair="GLOBAL"):
        adapter.critical("STARTUP_ABORT | reason=kill_switch_active")
        sys.exit(2)

    adapter.info("RUN_LIVE_GUARDED_START")

    # -------------------------------------------------
    # 2) LOGIN GATE (sets audit context + permissions)
    # -------------------------------------------------
    auth_ctx = await_login_ready_state()
    adapter.info(
        "LOGIN_BOUND | user_id=%s | role=%s | branch=%s",
        auth_ctx.user_id,
        auth_ctx.role,
        auth_ctx.current_branch,
    )

    # -------------------------------------------------
    # 3) Resolve execution entrypoint
    # -------------------------------------------------
    entrypoint = os.getenv("REA_ENGINE_ENTRYPOINT", "").strip()
    if not entrypoint:
        adapter.critical("ABORT | reason=REA_ENGINE_ENTRYPOINT_not_set")
        adapter.critical('Set REA_ENGINE_ENTRYPOINT like: "engine.run_engine:main"')
        sys.exit(3)

    adapter.info("ENTRYPOINT_BIND | %s", entrypoint)

    try:
        entry_fn = _resolve_entrypoint(entrypoint)
    except Exception as exc:
        adapter.critical("ENTRYPOINT_BIND_FAILED | %s", exc)
        sys.exit(4)

    # -------------------------------------------------
    # 4) Execute engine
    # -------------------------------------------------
    adapter.info("ENTRYPOINT_EXECUTE_START")
    start = time.time()

    try:
        entry_fn()
    except Exception as exc:
        adapter.critical("ENGINE_ABORT | reason=exception | %s", exc)
        raise
    finally:
        elapsed = time.time() - start
        adapter.info("RUN_LIVE_GUARDED_END | elapsed=%.2fs", elapsed)


if __name__ == "__main__":
    main()
