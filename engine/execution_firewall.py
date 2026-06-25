# tracked
"""
Execution Firewall – REA Capital Trading Engine
-----------------------------------------------

Purpose:
- Enforce LIVE vs TEST execution rules.
- Provide fail-closed protection in LIVE mode.
- Require dual-confirm override for LIVE execution.
- Produce structured, auditable firewall decisions.

Authoritative Rules:
- TEST mode: execution allowed if decision envelope ALLOW.
- LIVE mode: execution BLOCKED unless explicitly enabled.
- Overrides require two matching confirmations.
"""

from __future__ import annotations

import os
from typing import Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass


class ExecutionFirewallError(RuntimeError):
    pass


@dataclass(frozen=True)
class FirewallDecision:
    allowed: bool
    mode: str
    reason: str
    audit: Dict[str, Any]


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def evaluate_firewall(
    *,
    decision_allows_execution: bool,
    engine_mode: str,
    engine_run_id: str,
    override_confirm_1: bool | None = None,
    override_confirm_2: bool | None = None,
) -> Dict[str, Any]:
    """
    Returns structured firewall decision.
    """

    now = datetime.now(timezone.utc).isoformat()

    # Base envelope
    result = {
        "allowed": False,
        "mode": engine_mode,
        "reason": None,
        "audit": {
            "engine_run_id": engine_run_id,
            "timestamp_utc": now,
            "engine_mode": engine_mode,
        },
        "decision_allows_execution": False,
    }

    # Safety: envelope must allow first
    if not decision_allows_execution:
        result["reason"] = "firewall: decision envelope BLOCKED execution"
        return result

    # TEST MODE — always safe
    if engine_mode.upper() == "TEST":
        result.update(
            allowed=True,
            reason="firewall: TEST mode (execution simulated only)",
            decision_allows_execution=True,
        )
        return result

    # LIVE MODE — hard gate
    if engine_mode.upper() == "LIVE":

        # Global kill-switch
        if not _env_flag("LIVE_EXECUTION_ENABLED"):
            result["reason"] = "firewall: LIVE execution disabled (kill-switch)"
            return result

        # Dual-confirm override required
        if override_confirm_1 is not True or override_confirm_2 is not True:
            result["reason"] = (
                "firewall: LIVE override requires dual confirmation"
            )
            return result

        # Final allow
        result.update(
            allowed=True,
            reason="firewall: LIVE override confirmed (dual-confirm)",
            decision_allows_execution=True,
        )
        return result

    # Unknown mode
    result["reason"] = f"firewall: unknown engine mode '{engine_mode}'"
    return result


def check_execution_firewall(
    *,
    decision_allows_execution: bool,
    engine_run_id: str,
    engine_mode: str | None = None,
    override_confirm_1: bool | None = None,
    override_confirm_2: bool | None = None,
) -> FirewallDecision:
    """Compatibility wrapper for older callers expecting object attributes."""

    mode = str(engine_mode or os.getenv("ENGINE_MODE", "TEST")).strip().upper() or "TEST"
    payload = evaluate_firewall(
        decision_allows_execution=decision_allows_execution,
        engine_mode=mode,
        engine_run_id=engine_run_id,
        override_confirm_1=override_confirm_1,
        override_confirm_2=override_confirm_2,
    )
    return FirewallDecision(
        allowed=bool(payload.get("allowed", False)),
        mode=str(payload.get("mode", mode)),
        reason=str(payload.get("reason", "firewall: unknown")),
        audit=dict(payload.get("audit") or {}),
    )
