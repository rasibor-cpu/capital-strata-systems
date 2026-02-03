"""
engine/run_engine.py

Primary execution entrypoint for REA Capital Trading Engine.

Execution safety:
- Engine always starts in TEST mode unless REA_ENGINE_MODE=LIVE
- LIVE execution requires superuser (1369)
- LIVE gate enforced exactly once at execution boundary
"""

from __future__ import annotations

import time

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.audit_context import get_audit_context
from backend.app.security.live_toggle import require_live_allowed

log = get_logger("engine.run_engine")


def main() -> None:
    adapter = with_trace(log, "ENGINE")

    # Ensure audit context is present (login already completed)
    ctx = get_audit_context()
    adapter.info(
        "ENGINE_START | user_id=%s | role=%s | branch=%s",
        ctx.user_id,
        ctx.role,
        ctx.current_branch,
    )

    # HARD LIVE/TEST GATE (single authoritative check)
    require_live_allowed()

    adapter.critical("ENGINE_EXECUTION_BEGIN")

    # =============================
    # Existing engine loop preserved
    # =============================
    from engine.engine_loop import run_engine_loop

    start = time.time()
    run_engine_loop()
    elapsed = time.time() - start

    adapter.info("ENGINE_EXECUTION_END | elapsed=%.2fs", elapsed)
