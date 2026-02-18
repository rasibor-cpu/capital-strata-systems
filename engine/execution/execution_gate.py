"""
Execution Gate – Core Trade Validation Engine

Returns simple dict:
{
    "decision": "ALLOW" | "BLOCK",
    "reason": "text"
}

DecisionBuilder wraps into ExecutionDecision.

Fail-closed but exposes real exception reason for debugging.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.capital.compounding_engine import CompoundingEngine
from engine.risk.drawdown_scaler import DrawdownScaler
from engine.risk.risk_governor import RiskGovernor


HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT = 0.20


@dataclass(frozen=True)
class TradeIntent:
    instrument: str
    side: str
    notional: float
    stop_distance_pct: float
    policy: str = "core"


@dataclass(frozen=True)
class MarketContext:
    regime_persistence: Optional[float] = None


@dataclass(frozen=True)
class EquityContext:
    equity: float
    equity_peak: float


class ExecutionGate:
    def __init__(self) -> None:
        self.risk_governor = RiskGovernor()
        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()

    def evaluate_trade(
        self,
        *,
        intent: TradeIntent,
        eq: EquityContext,
        mkt: Optional[MarketContext] = None,
    ) -> dict:

        mkt = mkt or MarketContext()

        try:
            # -------- Basic validation --------
            if intent.notional <= 0:
                return {"decision": "BLOCK", "reason": "notional<=0"}

            if intent.stop_distance_pct <= 0:
                return {"decision": "BLOCK", "reason": "stop_distance_pct<=0"}

            if eq.equity <= 0:
                return {"decision": "BLOCK", "reason": "equity<=0"}

            # -------- Hard drawdown breaker --------
            if eq.equity_peak > 0:
                dd_pct = (eq.equity_peak - eq.equity) / eq.equity_peak
                if dd_pct >= HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT:
                    return {"decision": "BLOCK", "reason": "hard_drawdown_circuit_breaker"}

            # -------- Controlled compounding --------
            dyn_risk_pct = self.compounding.compute_dynamic_risk(
                equity=eq.equity,
                equity_peak=eq.equity_peak,
                regime_persistence=mkt.regime_persistence,
                policy=intent.policy,
            )

            if not dyn_risk_pct or dyn_risk_pct <= 0:
                return {"decision": "BLOCK", "reason": "dynamic_risk_pct<=0"}

            # -------- Drawdown compression --------
            scaled_risk_pct = self.drawdown_scaler.scale_risk_pct(
                base_risk_pct=dyn_risk_pct,
                equity=eq.equity,
                equity_peak=eq.equity_peak,
                policy=intent.policy,
            )

            if not scaled_risk_pct or scaled_risk_pct <= 0:
                return {"decision": "BLOCK", "reason": "scaled_risk_pct<=0"}

            # -------- Risk governor --------
            rg = self.risk_governor.validate_trade(
                instrument=intent.instrument,
                side=intent.side,
                requested_notional=intent.notional,
                stop_distance_pct=intent.stop_distance_pct,
                equity=eq.equity,
                risk_pct=scaled_risk_pct,
                policy=intent.policy,
            )

            ok = rg.get("ok", False) if isinstance(rg, dict) else getattr(rg, "ok", False)

            if not ok:
                return {"decision": "BLOCK", "reason": "risk_governor_reject"}

            return {"decision": "ALLOW", "reason": "all_checks_passed"}

        except Exception as e:
            return {"decision": "BLOCK", "reason": f"EXCEPTION: {type(e).__name__}: {e}"}
