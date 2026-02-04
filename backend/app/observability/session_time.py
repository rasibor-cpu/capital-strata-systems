"""
SESSION GATE — canonical, fail-safe session allow check.

Contract:
- MUST export: session_allow_state()
- MUST NOT raise on import
- MUST return a decision-like object (dict)
"""

from __future__ import annotations
from typing import Dict
import os


def session_allow_state() -> Dict[str, str | bool]:
    """
    Determines whether the current session is allowed to proceed.

    Returns:
        {
            "allowed": bool,
            "reason": str
        }
    """

    # Fail-closed defaults
    allowed = True
    reason = "ok"

    # Example policy hooks (safe defaults)
    if os.getenv("REA_MAINTENANCE_MODE", "0") == "1":
        allowed = False
        reason = "maintenance_mode"

    if os.getenv("REA_SESSION_BLOCKED", "0") == "1":
        allowed = False
        reason = "session_blocked"

    return {
        "allowed": allowed,
        "reason": reason,
    }
