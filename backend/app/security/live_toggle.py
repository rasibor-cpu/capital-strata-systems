"""
backend/app/security/live_toggle.py

Hard gate between TEST and LIVE execution.

Default:
- Engine runs in TEST mode
- LIVE must be explicitly armed by superuser

Fail-closed:
- Missing context or ambiguity => TEST only
"""

from __future__ import annotations

import os
import time

from backend.app.observability.logger import get_logger, with_trace
from backend.app.observability.audit_context import get_audit_context

log = get_logger("security.live_toggle")


def get_engine_mode() -> str:
    return os.getenv("REA_ENGINE_MODE", "TEST").upper().strip()


def is_live_mode() -> bool:
    return get_engine_mode() == "LIVE"


def require_live_allowed() -> None:
    """
    Call immediately before any REAL execution.
    """
    adapter = with_trace(log, "LIVE")

    ctx = get_audit_context()

    if not is_live_mode():
        adapter.info("EXECUTION_BLOCKED | mode=TEST")
        raise RuntimeError("EXECUTION_BLOCKED_TEST_MODE")

    # LIVE mode — superuser only
    if ctx.user_id != "1369":
        adapter.critical("LIVE_DENIED | user_id=%s | role=%s", ctx.user_id, ctx.role)
        raise PermissionError("LIVE_EXECUTION_DENIED")

    adapter.critical("LIVE_EXECUTION_ARMED | user_id=%s | at_utc=%s", ctx.user_id, time.time())
