"""
Concurrency Guard – REA Capital Trading Engine
----------------------------------------------

Purpose:
- Prevent exceeding maximum concurrent open positions.
- Safe defaults: missing or invalid inputs => BLOCK (fail-closed).

This module is intentionally adapter-agnostic. Caller supplies:
- current_open_positions (int)
- max_positions (int)

Returns a structured decision dict for audit + headless summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ConcurrencyDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class ConcurrencyPolicy:
    max_positions: int = 20


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None:
            return default
        # bool is subclass of int; reject it
        if isinstance(value, bool):
            return default
        return int(value)
    except Exception:
        return default


def evaluate_concurrency_guard(
    *,
    current_open_positions: Any,
    policy: ConcurrencyPolicy = ConcurrencyPolicy(),
) -> Dict[str, Any]:
    """
    Primary API (preferred): evaluate_concurrency_guard(...)
    """
    open_pos = _safe_int(current_open_positions, default=None)
    max_pos = _safe_int(policy.max_positions, default=None)

    # Fail-closed on invalid inputs
    if open_pos is None or max_pos is None or max_pos <= 0 or open_pos < 0:
        return {
            "decision": ConcurrencyDecision.BLOCK.value,
            "reason": "Invalid concurrency inputs (fail-closed).",
            "open_positions": open_pos if open_pos is not None else -1,
            "max_positions": max_pos if max_pos is not None else -1,
            "remaining": 0,
            "allowed": False,
        }

    remaining = max(0, max_pos - open_pos)
    allowed = open_pos < max_pos

    if allowed:
        return {
            "decision": ConcurrencyDecision.ALLOW.value,
            "reason": "Concurrency within limits.",
            "open_positions": open_pos,
            "max_positions": max_pos,
            "remaining": remaining,
            "allowed": True,
        }

    return {
        "decision": ConcurrencyDecision.BLOCK.value,
        "reason": "Max concurrent positions reached.",
        "open_positions": open_pos,
        "max_positions": max_pos,
        "remaining": 0,
        "allowed": False,
    }


# -------------------------------------------------------------------
# Backward-compat aliases (prevents import-name breakages)
# -------------------------------------------------------------------

def evaluate_concurrency(*, current_open_positions: Any, max_positions: Any = 20) -> Dict[str, Any]:
    """
    Compatibility wrapper: some callers import evaluate_concurrency.
    """
    policy = ConcurrencyPolicy(max_positions=_safe_int(max_positions, default=20) or 20)
    return evaluate_concurrency_guard(current_open_positions=current_open_positions, policy=policy)
