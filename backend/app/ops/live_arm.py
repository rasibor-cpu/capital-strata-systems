"""
backend/app/ops/live_arm.py

Hard safety latch for any live test / live use.

Rule (two-key):
- REA_LIVE_ARM=1
- REA_CONFIRM_LIVE=YES

If not both, live is NOT armed.

This is meant to be called by:
- engine entrypoint
- any future execution modules before placing orders
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from backend.app.observability.logger import get_logger, with_trace

log = get_logger("ops.live_arm")


@dataclass(frozen=True)
class LiveArmDecision:
    armed: bool
    reason: str


def live_armed() -> LiveArmDecision:
    arm = os.getenv("REA_LIVE_ARM", "").strip().lower()
    confirm = os.getenv("REA_CONFIRM_LIVE", "").strip().upper()

    if arm not in {"1", "true", "yes", "y", "on"}:
        return LiveArmDecision(False, "REA_LIVE_ARM_not_set")

    if confirm != "YES":
        return LiveArmDecision(False, "REA_CONFIRM_LIVE_not_yes")

    return LiveArmDecision(True, "armed")


def assert_live_armed_or_block() -> bool:
    """
    Returns True if armed. If not armed, logs and returns False.
    Fail-closed by default (caller should block live actions).
    """
    d = live_armed()
    adapter = with_trace(log, "ARM")
    if d.armed:
        adapter.info("LIVE_ARM_OK | reason=%s", d.reason)
        return True

    adapter.warning("LIVE_ARM_BLOCK | reason=%s", d.reason)
    return False
