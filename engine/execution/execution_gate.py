"""
execution_gate.py
-----------------
Authoritative execution gate for REA Capital Trading Engine.

FAIL-CLOSED by default.
Execution is ALLOWED only when ALL governance conditions are met.

Single source of truth:
- audit/live_state.json

This gate must never infer, guess, or auto-escalate.
"""

import json
import os
from datetime import datetime, timezone


LIVE_STATE_PATH = os.path.join("audit", "live_state.json")


class ExecutionGateResult:
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


def _utcnow():
    return datetime.now(timezone.utc)


def _load_live_state():
    if not os.path.exists(LIVE_STATE_PATH):
        return None, "live_state_missing"

    try:
        with open(LIVE_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except Exception as e:
        return None, f"live_state_unreadable:{e}"


def execution_gate_check():
    """
    Returns:
        (ALLOW|BLOCK, reason:str)

    Governance rules (ALL required):
    - state == ARMED_ACTIVE
    - expires_at_utc is None OR now < expires_at_utc
    - preflight_passed == True
    - rate_limit_ok == True
    """

    state, err = _load_live_state()
    if err:
        return ExecutionGateResult.BLOCK, f"execution_gate_error_{err}_fail_closed"

    # ---- Required fields (fail closed if missing) ----
    armed_state = state.get("state")
    expires_at = state.get("expires_at_utc")
    preflight_ok = state.get("preflight_passed")
    rate_limit_ok = state.get("rate_limit_ok")

    # ---- State check ----
    if armed_state != "ARMED_ACTIVE":
        return ExecutionGateResult.BLOCK, f"not_armed({armed_state})"

    # ---- Expiry check ----
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if _utcnow() >= exp:
                return ExecutionGateResult.BLOCK, "armed_state_expired"
        except Exception:
            return ExecutionGateResult.BLOCK, "invalid_expiry_format"

    # ---- Preflight check ----
    if preflight_ok is not True:
        return ExecutionGateResult.BLOCK, "preflight_not_passed"

    # ---- Rate limit check ----
    if rate_limit_ok is not True:
        return ExecutionGateResult.BLOCK, "rate_limit_blocked"

    return ExecutionGateResult.ALLOW, "execution_gate_allow_all_conditions_met"


# CLI / smoke-test support
if __name__ == "__main__":
    verdict, reason = execution_gate_check()
    print("EXECUTION_GATE:", verdict)
    print("REASON:", reason)
