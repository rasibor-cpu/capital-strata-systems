"""
Risk Guard Adapter
==================

Purpose:
- Provide the risk_guard callable declared by engine/gates_registry.py
- Normalize generic GateInputs into the canonical RiskGovernor.validate_trade
- Fail closed when required risk inputs are absent or malformed
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from engine.decision_builder import GateInputs


def evaluate_risk(inputs: GateInputs) -> Dict[str, str]:
    try:
        risk = inputs.risk
        if not isinstance(risk, dict):
            return _block("risk_guard: missing risk dict")

        side = _text(risk.get("side"))
        notional = _number(
            risk.get("requested_notional", risk.get("notional", risk.get("trade_size")))
        )
        stop_distance_pct = _number(
            risk.get("stop_distance_pct", risk.get("stop_pct", risk.get("stop_distance")))
        )
        equity = _number(risk.get("equity"))

        missing = []
        if not side:
            missing.append("side")
        if notional is None:
            missing.append("notional")
        if stop_distance_pct is None:
            missing.append("stop_distance_pct")
        if equity is None:
            missing.append("equity")
        if missing:
            return _block(f"risk_guard: missing required risk inputs: {','.join(missing)}")

        from engine.risk.risk_governor import RiskGovernor

        decision = RiskGovernor().validate_trade(
            instrument=str(inputs.instrument),
            side=side,
            requested_notional=float(notional),
            stop_distance_pct=float(stop_distance_pct),
            equity=float(equity),
            policy=str(risk.get("policy", "core") or "core"),
        )

        reason = str(getattr(decision, "reason", "risk_guard_decision"))
        if bool(getattr(decision, "ok", False)):
            return _allow(reason)
        return _block(reason)

    except Exception as exc:
        return _block(f"risk_guard: EXCEPTION {type(exc).__name__}: {exc}")


def _text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _allow(reason: str) -> Dict[str, str]:
    return {"decision": "ALLOW", "reason": reason}


def _block(reason: str) -> Dict[str, str]:
    return {"decision": "BLOCK", "reason": reason}

