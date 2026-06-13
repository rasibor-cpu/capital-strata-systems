"""
SuperExecutionGateAdapter
Capital Strata Systems

Purpose:
- Provide a stable adapter interface for ExecutionGate across runners/tests
- Centralize context -> gate argument wiring
- Keep gate fail-closed; adapter is "best-effort" on optional fields

NEW (v3.8):
- Wires weekly rebalance inputs into ExecutionGate.evaluate_trade:
  - current_allocations
  - rebalance_target_weights
  - volatility_state
  - regime_state
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from engine.execution.execution_gate import ExecutionGate


# -------------------------
# Minimal type shells (keeps adapter stable even if your project
# defines these elsewhere with richer fields).
# If your repo already defines these, imports in callers may override usage.
# -------------------------

@dataclass
class TradeIntent:
    instrument: str
    side: str
    notional: float
    stop_distance_pct: float


@dataclass
class EquityContext:
    equity: float
    equity_peak: float = 0.0
    # Optional fields used by rebalance:
    current_allocations: Optional[Dict[str, float]] = None
    rebalance_target_weights: Optional[Dict[str, float]] = None


@dataclass
class MarketContext:
    regime_persistence: float = 0.0
    policy: str = "core"
    # Optional fields used by rebalance:
    regime_state: str = "NORMAL"
    volatility_state: str = "MEDIUM"
    expected_move_bps: Optional[float] = None
    fee_bps: Optional[float] = None
    spread_bps: Optional[float] = None
    slippage_bps: Optional[float] = None


# -------------------------
# helpers
# -------------------------

def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Safe getattr/dict-get with fallback."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_dict_float(x: Any) -> Optional[Dict[str, float]]:
    if x is None:
        return None
    if isinstance(x, dict):
        out: Dict[str, float] = {}
        for k, v in x.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
        return out
    return None


class SuperExecutionGateAdapter:
    """
    Adapter that calls ExecutionGate with the canonical flat interface.
    """

    def __init__(self) -> None:
        self._gate = ExecutionGate()

    def evaluate(
        self,
        *,
        intent: Any,
        equity_ctx: Any,
        market_ctx: Any,
        execution_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Returns ExecutionGate decision envelope:
          {"decision": {"final": "ALLOW"|"BLOCK"}, "reason": "...", "debug": {...}}

        execution_enabled=False can be used by tests/runners to force BLOCK
        without changing gate logic (institutional-safe toggle).
        """
        if not execution_enabled:
            return {"decision": {"final": "BLOCK"}, "reason": "execution_disabled", "debug": {"adapter": "super_gate"}}

        instrument = _get(intent, "instrument", "")
        side = _get(intent, "side", "")
        notional = float(_get(intent, "notional", 0.0) or 0.0)
        stop_distance_pct = float(_get(intent, "stop_distance_pct", 0.0) or 0.0)

        equity = float(_get(equity_ctx, "equity", 0.0) or 0.0)
        equity_peak = float(_get(equity_ctx, "equity_peak", 0.0) or 0.0)

        regime_persistence = float(_get(market_ctx, "regime_persistence", 0.0) or 0.0)
        policy = _get(market_ctx, "policy", "core") or "core"

        # -------- Weekly rebalance wiring (optional) --------
        current_allocations = _as_dict_float(
            _get(equity_ctx, "current_allocations", None) or _get(market_ctx, "current_allocations", None)
        )

        rebalance_target_weights = _as_dict_float(
            _get(equity_ctx, "rebalance_target_weights", None)
            or _get(market_ctx, "rebalance_target_weights", None)
            or _get(market_ctx, "target_weights", None)
        )

        volatility_state = _get(market_ctx, "volatility_state", "MEDIUM") or "MEDIUM"
        regime_state = _get(market_ctx, "regime_state", "NORMAL") or "NORMAL"
        expected_move_bps = _get(market_ctx, "expected_move_bps", None)
        fee_bps = _get(market_ctx, "fee_bps", None)
        spread_bps = _get(market_ctx, "spread_bps", None)
        slippage_bps = _get(market_ctx, "slippage_bps", None)

        # Call the gate (flat interface)
        return self._gate.evaluate_trade(
            instrument=instrument,
            side=side,
            notional=notional,
            stop_distance_pct=stop_distance_pct,
            equity=equity,
            equity_peak=equity_peak,
            regime_persistence=regime_persistence,
            policy=policy,
            # new optional args (safe defaults in gate)
            current_allocations=current_allocations,
            rebalance_target_weights=rebalance_target_weights,
            volatility_state=volatility_state,
            regime_state=regime_state,
            expected_move_bps=expected_move_bps,
            fee_bps=fee_bps,
            spread_bps=spread_bps,
            slippage_bps=slippage_bps,
        )
