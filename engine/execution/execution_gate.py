"""
Execution Gate – Canonical Flat Interface
Capital Strata Systems

Flat interface for EngineLoop compatibility.
Fail-closed with structured debug.
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from engine.capital.compounding_engine import CompoundingEngine
from engine.risk.drawdown_scaler import DrawdownScaler
from engine.risk.risk_governor import RiskGovernor


HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT = 0.20


class ExecutionGate:
    def __init__(self) -> None:
        self.risk_governor = RiskGovernor()
        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()

    def evaluate_trade(
        self,
        *,
        instrument: str,
        side: str,
        notional: float,
        stop_distance_pct: float,
        equity: float,
        equity_peak: float,
        regime_persistence: float,
        policy: str = "core",
    ) -> Dict[str, Any]:

        try:
            # ---------------- Basic validation ----------------
            if notional <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "notional<=0"}

            if stop_distance_pct <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "stop_distance_pct<=0"}

            if equity <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "equity<=0"}

            # ---------------- Hard circuit breaker ----------------
            if equity_peak > 0:
                dd_pct = (equity_peak - equity) / equity_peak
                if dd_pct >= HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT:
                    return {
                        "decision": {"final": "BLOCK"},
                        "reason": "hard_drawdown_circuit_breaker",
                    }

            # ---------------- Compounding ----------------
            dynamic_risk_pct = self.compounding.compute_dynamic_risk(
                equity=equity,
                equity_peak=equity_peak,
                regime_persistence=regime_persistence,
            )

            if dynamic_risk_pct <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "dynamic_risk_pct<=0"}

            # ---------------- Drawdown Scaling ----------------
            dd_result = self.drawdown_scaler.evaluate(
                equity=equity,
                equity_peak=equity_peak,
            )

            if dd_result.hard_stop:
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": "drawdown_scaler_hard_stop",
                }

            scaled_risk_pct = dynamic_risk_pct * dd_result.multiplier

            if scaled_risk_pct <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "scaled_risk_pct<=0"}

            # ---------------- Risk Governor ----------------
            rg = self.risk_governor.validate_trade(
                instrument=instrument,
                side=side,
                requested_notional=notional,
                stop_distance_pct=stop_distance_pct,
                equity=equity,
                risk_pct=scaled_risk_pct,
                policy=policy,
            )

            if not rg.get("ok", False):
                return {
                    "decision": {"final": "BLOCK"},
                    "reason": rg.get("reason", "risk_governor_reject"),
                }

            return {
                "decision": {
                    "final": "ALLOW",
                    "compounding": {
                        "applied": dynamic_risk_pct > self.compounding.profile.base_risk_pct
                    },
                },
                "reason": "approved",
            }

        except Exception as e:
            return {
                "decision": {"final": "BLOCK"},
                "reason": "execution_gate_exception",
                "debug": f"{type(e).__name__}: {e}",
            }
