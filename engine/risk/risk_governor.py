"""
Risk Governor – Central Risk Policy Layer
Capital Strata Systems / REA Capital Trading Engine

Fail-closed by design.

Now includes:
- Adaptive Portfolio Cap Scaling (dynamic risk + notional caps)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TradeRequest:
    instrument: str
    side: str  # "buy" / "sell"
    notional: float
    stop_distance_pct: float  # used to approximate risk, e.g. 0.01 for 1%
    policy: str = "core"


@dataclass
class RiskDecision:
    ok: bool
    reasons: List[str]
    caps: Dict[str, Any]
    timestamp_utc: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": self.reasons,
            "caps": self.caps,
            "timestamp_utc": self.timestamp_utc,
        }


class RiskGovernor:
    """
    Phase 1 in-memory risk governor.

    Assumes you track:
      equity, equity_peak, cooldown_active, trades_today, daily_pnl, consecutive_losses
    """

    # Hard failsafes
    MAX_TRADES_PER_DAY = 8
    MAX_CONSECUTIVE_LOSSES = 3

    # If daily loss exceeds this fraction of equity, we halt
    MAX_DAILY_LOSS_PCT = 0.02  # 2%

    def __init__(self) -> None:
        self.state: Dict[str, Any] = {
            "day_key": "1970-01-01",
            "equity": 100000.0,
            "equity_peak": 100000.0,
            "trades_today": 0,
            "daily_pnl": 0.0,
            "consecutive_losses": 0,
            "cooldown_active": False,
            "regime": "normal",  # "normal" / "cautious" / "aggressive"
        }

    def set_day(self, day_key: str) -> None:
        if day_key != self.state.get("day_key"):
            self.state["day_key"] = day_key
            self.state["trades_today"] = 0
            self.state["daily_pnl"] = 0.0
            self.state["consecutive_losses"] = 0

    def update_equity(self, equity: float) -> None:
        self.state["equity"] = float(equity)
        if self.state["equity"] > self.state.get("equity_peak", 0.0):
            self.state["equity_peak"] = float(self.state["equity"])

    def set_regime(self, regime: str) -> None:
        self.state["regime"] = str(regime)

    def set_cooldown(self, active: bool) -> None:
        self.state["cooldown_active"] = bool(active)

    def record_trade_outcome(self, pnl: float) -> None:
        self.state["daily_pnl"] = float(self.state.get("daily_pnl", 0.0)) + float(pnl)
        if pnl < 0:
            self.state["consecutive_losses"] = int(self.state.get("consecutive_losses", 0)) + 1
        else:
            self.state["consecutive_losses"] = 0

    def allow_trade(self, req: TradeRequest) -> RiskDecision:
        reasons: List[str] = []
        ts = _utc_now_iso()

        # Basic validations (fail-closed)
        if req.notional <= 0:
            return RiskDecision(False, ["invalid_notional"], {}, ts)

        if req.stop_distance_pct <= 0 or req.stop_distance_pct >= 0.25:
            return RiskDecision(False, ["invalid_stop_distance_pct"], {}, ts)

        equity = float(self.state.get("equity", 0.0))
        equity_peak = float(self.state.get("equity_peak", 0.0))
        cooldown_active = bool(self.state.get("cooldown_active", False))
        regime = str(self.state.get("regime", "normal"))

        trades_today = int(self.state.get("trades_today", 0))
        daily_pnl = float(self.state.get("daily_pnl", 0.0))
        consecutive_losses = int(self.state.get("consecutive_losses", 0))

        # Global halts
        if trades_today >= self.MAX_TRADES_PER_DAY:
            return RiskDecision(False, ["max_trades_per_day_reached"], {}, ts)

        if consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            return RiskDecision(False, ["max_consecutive_losses_reached"], {}, ts)

        if equity <= 0:
            return RiskDecision(False, ["invalid_equity_fail_closed"], {}, ts)

        if daily_pnl < 0 and abs(daily_pnl) / equity >= self.MAX_DAILY_LOSS_PCT:
            return RiskDecision(False, ["max_daily_loss_reached"], {}, ts)

        # Adaptive Cap Scaling (core)
        caps: Dict[str, Any] = {}
        try:
            from engine.capital.adaptive_cap_scaler import AdaptiveCapScaler  # type: ignore

            scaler = AdaptiveCapScaler()
            cap_dec = scaler.compute(
                equity=equity,
                equity_peak=equity_peak,
                regime=regime,
                cooldown_active=cooldown_active,
            )
            caps = cap_dec.as_dict()
            reasons.extend(cap_dec.reasons)

            # Convert caps to absolute limits
            risk_budget_abs = caps["risk_budget_pct"] * equity
            max_notional_abs = caps["max_position_notional_pct"] * equity

            # Approximate trade risk = notional * stop_distance_pct
            approx_risk_abs = req.notional * req.stop_distance_pct

            if req.notional > max_notional_abs:
                reasons.append("notional_exceeds_dynamic_cap")
                return RiskDecision(False, reasons, caps, ts)

            if approx_risk_abs > risk_budget_abs:
                reasons.append("risk_exceeds_dynamic_budget")
                return RiskDecision(False, reasons, caps, ts)

        except Exception as e:
            return RiskDecision(
                False,
                ["cap_scaler_error_fail_closed", f"{type(e).__name__}"],
                {"error": str(e)},
                ts,
            )

        # Approved
        self.state["trades_today"] = trades_today + 1
        reasons.append("approved")
        return RiskDecision(True, reasons, caps, ts)


def apply_trade(governor: RiskGovernor, req_dict: Dict[str, Any]) -> Dict[str, Any]:
    req = TradeRequest(
        instrument=str(req_dict.get("instrument", "")),
        side=str(req_dict.get("side", "")),
        notional=float(req_dict.get("notional", 0.0)),
        stop_distance_pct=float(req_dict.get("stop_distance_pct", 0.0)),
        policy=str(req_dict.get("policy", "core")),
    )
    decision = governor.allow_trade(req)
    return decision.as_dict()
