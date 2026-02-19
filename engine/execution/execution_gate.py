"""
Execution Gate – Canonical Flat Interface
Capital Strata Systems

Flat interface for EngineLoop compatibility.
Fail-closed with structured debug.

Weekly Rebalance enforcement (dynamic drift):
- If Friday 17:00 ET window AND drift threshold exceeded => BLOCK new trades.
- Does NOT mutate capital mid-session. Enforcement only.

Upgrade (EquityAuthority integration):
- Supports injected RiskGovernor (preferred)
- If governor is bound to EquityAuthority, validate_trade will NOT receive equity input
  (prevents shadow equity and eliminates ok_input_fallback mode).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from engine.capital.compounding_engine import CompoundingEngine
from engine.risk.drawdown_scaler import DrawdownScaler
from engine.risk.risk_governor import RiskGovernor
from engine.capital.weekly_rebalance_engine import WeeklyRebalanceEngine

HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT = 0.20


class ExecutionGate:
    def __init__(self, risk_governor: Optional[RiskGovernor] = None) -> None:
        # Prefer injected governor (authority-bound). Fall back to default for legacy callers.
        self.risk_governor = risk_governor or RiskGovernor()
        self.compounding = CompoundingEngine()
        self.drawdown_scaler = DrawdownScaler()
        self._rebalance_engine: Optional[WeeklyRebalanceEngine] = None

    # --------------------------------------------------------
    # Rebalance Enforcement
    # --------------------------------------------------------

    def _rebalance_check(
        self,
        *,
        now_utc: datetime,
        current_allocations: Optional[Dict[str, float]],
        target_weights: Optional[Dict[str, float]],
        volatility_state: str,
        regime_state: str,
        debug: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:

        if not target_weights:
            debug["rebalance"] = {"skipped": True, "reason": "no_target_weights"}
            return None

        if self._rebalance_engine is None or getattr(self._rebalance_engine, "target_weights", None) != target_weights:
            self._rebalance_engine = WeeklyRebalanceEngine(target_weights=target_weights)

        res = self._rebalance_engine.evaluate(
            now_utc=now_utc,
            current_allocations=current_allocations or {},
            volatility_state=volatility_state,
            regime_state=regime_state,
        )

        debug["rebalance"] = {
            "should_rebalance": res.should_rebalance,
            "reason": res.reason,
            "effective_threshold": res.effective_threshold,
            "drift": res.drift_snapshot,
        }

        if res.should_rebalance:
            return {"decision": {"final": "BLOCK"}, "reason": "weekly_rebalance_window_active", "debug": debug}

        return None

    # --------------------------------------------------------
    # Main Evaluation
    # --------------------------------------------------------

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
        current_allocations: Optional[Dict[str, float]] = None,
        rebalance_target_weights: Optional[Dict[str, float]] = None,
        volatility_state: str = "MEDIUM",
        regime_state: str = "NORMAL",
    ) -> Dict[str, Any]:

        debug: Dict[str, Any] = {"instrument": instrument, "side": side}

        try:

            # -------------------------
            # Basic validation
            # -------------------------
            if notional <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "notional_invalid", "debug": debug}

            if stop_distance_pct <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "stop_distance_invalid", "debug": debug}

            if equity <= 0:
                return {"decision": {"final": "BLOCK"}, "reason": "equity_invalid", "debug": debug}

            # -------------------------
            # Hard circuit breaker
            # -------------------------
            if equity_peak > 0:
                dd_pct = (equity_peak - equity) / equity_peak
                if dd_pct >= HARD_DRAWDOWN_CIRCUIT_BREAKER_PCT:
                    return {
                        "decision": {"final": "BLOCK"},
                        "reason": "hard_drawdown_circuit_breaker",
                        "debug": {"drawdown_pct": dd_pct},
                    }

            # -------------------------
            # Weekly Rebalance
            # -------------------------
            now_utc = datetime.utcnow()
            block = self._rebalance_check(
                now_utc=now_utc,
                current_allocations=current_allocations,
                target_weights=rebalance_target_weights,
                volatility_state=volatility_state,
                regime_state=regime_state,
                debug=debug,
            )
            if block:
                return block

            # -------------------------
            # Compounding
            # -------------------------
            risk_pct = self.compounding.compute_dynamic_risk(
                equity=equity,
                equity_peak=equity_peak,
                regime_persistence=regime_persistence,
            )

            debug["risk_pct"] = risk_pct

            # -------------------------
            # Drawdown Scaling
            # -------------------------
            scaled_notional = notional
            try:
                scaled_notional = self.drawdown_scaler.scale(
                    notional=notional,
                    equity=equity,
                    equity_peak=equity_peak,
                    policy=policy,
                )
            except Exception:
                pass

            debug["scaled_notional"] = scaled_notional

            # -------------------------
            # RiskGovernor (validate_trade)
            # -------------------------
            # If governor is authority-bound, do NOT pass equity (prevents shadow equity & fallback mode).
            gov = self.risk_governor
            use_authority = bool(getattr(gov, "equity_authority", None) is not None)

            if use_authority:
                decision = gov.validate_trade(
                    instrument=instrument,
                    side=side,
                    requested_notional=scaled_notional,
                    stop_distance_pct=stop_distance_pct,
                    equity=0.0,           # ignored by authority path; kept for signature stability
                    risk_pct=risk_pct,
                    policy=policy,
                )
            else:
                decision = gov.validate_trade(
                    instrument=instrument,
                    side=side,
                    requested_notional=scaled_notional,
                    stop_distance_pct=stop_distance_pct,
                    equity=equity,
                    risk_pct=risk_pct,
                    policy=policy,
                )

            debug["governor_response"] = decision

            if not decision.get("ok", False):
                return {"decision": {"final": "BLOCK"}, "reason": decision.get("reason", "governor_reject"), "debug": debug}

            return {"decision": {"final": "ALLOW"}, "reason": "approved", "debug": debug}

        except Exception as e:
            return {"decision": {"final": "BLOCK"}, "reason": "execution_gate_exception", "debug": {"exception": str(e)}}
