# engine/execution/execution_gate.py
"""
Execution Gate — HARD GOVERNANCE LOCK (FAIL-CLOSED)

Final authority before any execution.

ALLOW only if ALL pass:
1) execution_policy.json loads + validates
2) instrument is whitelisted
3) risk_pct <= max_equity_risk_per_trade_pct
4) live_state == ARMED_ACTIVE and not expired
5) rate-limit OK
6) no auto-disarm reason
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List

from engine.execution.execution_policy_loader import load_execution_policy
from engine.execution.live_state import get_live_state
from engine.execution.rate_limiter import check_rate_limit
from engine.execution.auto_disarm import check_auto_disarm


class ExecutionGateDecision:
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


def _flatten_whitelist(wl: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for k in ("fx", "crypto", "equities", "options"):
        v = wl.get(k, [])
        if isinstance(v, list):
            out.extend([str(x).upper() for x in v])
    return out


def execution_gate_check(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    context expects:
      - instrument: str (e.g., EURUSD)
      - risk_pct: float (0..100) intended equity risk for this trade
    """
    # FAIL-CLOSED default
    result = {
        "decision": ExecutionGateDecision.BLOCK,
        "reason": "unknown",
        "ts": datetime.now(timezone.utc).isoformat(),
        "meta": {},
    }

    instrument = str(context.get("instrument", "")).upper().strip()
    risk_pct = float(context.get("risk_pct", 0.0) or 0.0)

    # 1) Load policy (validated)
    try:
        policy = load_execution_policy()
    except Exception as e:
        result["reason"] = f"policy_load_failed: {e}"
        return result

    # 2) Instrument whitelist
    wl = policy.get("instrument_whitelist", {})
    allowed_instruments = _flatten_whitelist(wl)
    if not instrument or instrument not in allowed_instruments:
        result["reason"] = "instrument_not_whitelisted"
        result["meta"] = {"instrument": instrument}
        return result

    # 3) Risk cap per trade
    cap = policy.get("capital_protection", {})
    max_risk = float(cap.get("max_equity_risk_per_trade_pct", 0.0) or 0.0)
    if risk_pct > max_risk:
        result["reason"] = "risk_pct_exceeds_policy"
        result["meta"] = {"risk_pct": risk_pct, "max_allowed_pct": max_risk}
        return result

    # 4) Live state must be ARMED_ACTIVE
    ls = get_live_state()
    if ls.state != "ARMED_ACTIVE":
        result["reason"] = f"not_armed ({ls.state})"
        result["meta"] = {"armed_state": ls.state}
        return result
    if ls.is_expired():
        result["reason"] = "arming_expired"
        result["meta"] = {"expires_at_utc": ls.expires_at_utc}
        return result

    # 5) Rate limit
    if not check_rate_limit():
        result["reason"] = "rate_limit_exceeded"
        return result

    # 6) Auto-disarm checks
    disarm_reason = check_auto_disarm()
    if disarm_reason:
        result["reason"] = f"auto_disarm: {disarm_reason}"
        return result

    # ✅ All pass
    result["decision"] = ExecutionGateDecision.ALLOW
    result["reason"] = "ok"
    result["meta"] = {"instrument": instrument, "risk_pct": risk_pct}
    return result
