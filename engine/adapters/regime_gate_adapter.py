"""
Regime Gate Adapter – Wired to RegimeGate().evaluate(...)
========================================================

Authoritative module:
  engine/regime/regime_gate.py

Discovered callable and signature:
  RegimeGate().evaluate(
      *,
      bars_5m: int,
      vol_norm_0_1: float | None = None,
      spread_bps: float | None = None,
      high_risk_news: bool | None = None,
      extra: dict | None = None
  ) -> RegimeDecision

This adapter maps GateInputs -> that signature in a fail-closed way.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from engine.decision_builder import GateInputs


def evaluate_regime(inputs: GateInputs) -> Dict[str, str]:
    try:
        import engine.regime.regime_gate as m

        gate = m.RegimeGate()

        # REQUIRED
        bars_5m = _extract_bars_5m(inputs.snapshot)
        if bars_5m is None:
            return {
                "decision": "BLOCK",
                "reason": "regime_gate_adapter: MISSING_REQUIRED bars_5m (set snapshot['bars_5m'])",
            }

        # OPTIONALS
        vol_norm = _extract_vol_norm(inputs.volatility)
        spread_bps = _extract_spread_bps(inputs.liquidity, inputs.snapshot)
        high_risk_news = _extract_high_risk_news(inputs)

        extra = {
            "instrument": inputs.instrument,
            "snapshot_keys": sorted(list(inputs.snapshot.keys())) if isinstance(inputs.snapshot, dict) else None,
            "volatility_keys": sorted(list(inputs.volatility.keys())) if isinstance(inputs.volatility, dict) else None,
            "liquidity_keys": sorted(list(inputs.liquidity.keys())) if isinstance(inputs.liquidity, dict) else None,
        }

        raw = gate.evaluate(
            bars_5m=int(bars_5m),
            vol_norm_0_1=vol_norm,
            spread_bps=spread_bps,
            high_risk_news=high_risk_news,
            extra=extra,
        )
        return _normalize(raw)

    except Exception as e:
        return {
            "decision": "BLOCK",
            "reason": f"regime_gate_adapter: EXCEPTION {type(e).__name__}: {e}",
        }


def _extract_bars_5m(snapshot: Any) -> Optional[int]:
    if not isinstance(snapshot, dict):
        return None
    for k in ("bars_5m", "bars_5m_count", "bars5m", "count_5m", "bars5m_count"):
        v = snapshot.get(k)
        if isinstance(v, int) and v >= 0:
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return None


def _extract_vol_norm(volatility: Any) -> Optional[float]:
    if not isinstance(volatility, dict):
        return None
    for k in ("vol_norm_0_1", "vol_norm", "vol_norm01"):
        v = volatility.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _extract_spread_bps(liquidity: Any, snapshot: Any) -> Optional[float]:
    if not isinstance(liquidity, dict):
        return None

    # Best: already bps
    v = liquidity.get("spread_bps")
    if isinstance(v, (int, float)):
        return float(v)

    # Heuristic: convert price spread -> bps using mid/price if available
    spread = liquidity.get("spread")
    if not isinstance(spread, (int, float)):
        return None

    mid = liquidity.get("mid") or liquidity.get("price") or liquidity.get("mid_price")
    if not isinstance(mid, (int, float)) and isinstance(snapshot, dict):
        mid = snapshot.get("price") or snapshot.get("mid") or snapshot.get("mid_price")

    if isinstance(mid, (int, float)) and float(mid) > 0:
        return (float(spread) / float(mid)) * 10000.0

    return None


def _extract_high_risk_news(inputs: GateInputs) -> Optional[bool]:
    if isinstance(inputs.snapshot, dict):
        v = inputs.snapshot.get("high_risk_news")
        if isinstance(v, bool):
            return v

    if isinstance(inputs.risk, dict):
        v = inputs.risk.get("high_risk_news")
        if isinstance(v, bool):
            return v

    if isinstance(inputs.volatility, dict):
        v = inputs.volatility.get("high_risk_news")
        if isinstance(v, bool):
            return v

    return None


def _normalize(raw: Any) -> Dict[str, str]:
    # Dict
    if isinstance(raw, dict):
        decision = str(raw.get("decision", "BLOCK")).upper()
        reason = str(raw.get("reason", "REGIME_DECISION"))
        return {"decision": decision, "reason": reason}

    # Object (likely RegimeDecision)
    if hasattr(raw, "decision"):
        decision = str(getattr(raw, "decision", "BLOCK")).upper()
        reason = str(getattr(raw, "reason", "REGIME_DECISION"))
        return {"decision": decision, "reason": reason}

    # Tuple/list
    if isinstance(raw, (tuple, list)) and len(raw) >= 1:
        decision = str(raw[0]).upper()
        reason = str(raw[1]) if len(raw) >= 2 else "REGIME_DECISION"
        return {"decision": decision, "reason": reason}

    # String
    s = str(raw).upper().strip()
    if s in ("ALLOW", "BLOCK", "WARN"):
        return {"decision": s, "reason": "REGIME_DECISION"}

    return {"decision": "BLOCK", "reason": "REGIME_GATE_UNRECOGNIZED_OUTPUT"}
