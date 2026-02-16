"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems

Stack Order:
Volatility → Regime → AdaptiveCapital → RiskGovernor

Fail-closed by design.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from engine.risk.risk_state_store import load_state, save_state
from engine.capital.adaptive_capital import AdaptiveCapitalEngine


class ExecutionGate:
    def __init__(self) -> None:

        from engine.risk.risk_governor import RiskGovernor  # lazy import

        self.risk_governor = RiskGovernor()
        self.capital_engine = AdaptiveCapitalEngine()

        persisted = load_state()
        if isinstance(persisted, dict) and persisted:
            if hasattr(self.risk_governor, "state"):
                self.risk_governor.state.update(persisted)

        self.state: Dict[str, Any] = getattr(self.risk_governor, "state", {})

        if "open_positions" not in self.state:
            self.state["open_positions"] = 0

    # ---------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------

    def _persist(self) -> None:
        save_state(self.state)

    def snapshot(self, instrument: str) -> Dict[str, Any]:
        return {
            "instrument": instrument,
            "day_key": self.state.get("day_key"),
            "equity": self.state.get("equity"),
            "equity_peak": self.state.get("equity_peak"),
            "trades_today": self.state.get("trades_today"),
            "daily_pnl": self.state.get("daily_pnl"),
            "consecutive_losses": self.state.get("consecutive_losses"),
            "cooldown_active": self.state.get("cooldown_active"),
            "regime": self.state.get("regime"),
            "open_positions": self.state.get("open_positions"),
        }

    # ---------------------------------------------------------
    # Core Evaluation
    # ---------------------------------------------------------

    def evaluate_trade(
        self,
        *,
        instrument: str,
        side: Optional[str] = None,
        notional: Optional[float] = None,
        stop_distance_pct: Optional[float] = None,
        policy: str = "core",
        volatility_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:

        # -------------------------------
        # Probe Mode (fail-soft)
        # -------------------------------
        if side is None or notional is None or stop_distance_pct is None:
            return {
                "status": "REJECTED",
                "decision": {
                    "ok": False,
                    "reason": "missing_required_fields",
                    "missing": [
                        x for x in ["side", "notional", "stop_distance_pct"]
                        if locals()[x] is None
                    ],
                },
                "snapshot": self.snapshot(instrument),
            }

        # -------------------------------
        # Capital Multiplier Layer
        # -------------------------------
        capital_result = self.capital_engine.compute_multiplier(
            equity=self.state.get("equity"),
            equity_peak=self.state.get("equity_peak"),
            consecutive_losses=self.state.get("consecutive_losses") or 0,
            regime=self.state.get("regime"),
            volatility_ratio=volatility_ratio,
        )

        multiplier = capital_result["multiplier"]

        if multiplier <= 0:
            return {
                "status": "REJECTED",
                "decision": {
                    "ok": False,
                    "reason": "capital_multiplier_zero",
                    "capital_reason": capital_result["reason"],
                },
                "snapshot": self.snapshot(instrument),
            }

        adjusted_notional = float(notional) * float(multiplier)

        # -------------------------------
        # RiskGovernor Layer
        # -------------------------------
        try:
            from engine.risk.risk_governor import TradeRequest

            req = TradeRequest(
                instrument=instrument,
                side=side,
                notional=adjusted_notional,
                stop_distance_pct=stop_distance_pct,
                policy=policy,
            )

            dec = self.risk_governor.allow_trade(req).as_dict()

        except Exception as e:
            return {
                "status": "REJECTED",
                "decision": {
                    "ok": False,
                    "reason": "allow_trade_exception",
                    "error": str(e),
                },
                "snapshot": self.snapshot(instrument),
            }

        if not dec.get("ok", False):
            return {
                "status": "REJECTED",
                "decision": dec,
                "snapshot": self.snapshot(instrument),
            }

        self.state["open_positions"] += 1
        self._persist()

        return {
            "status": "APPROVED",
            "decision": dec,
            "capital_multiplier": multiplier,
            "adjusted_notional": adjusted_notional,
            "snapshot": self.snapshot(instrument),
        }
