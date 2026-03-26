from __future__ import annotations

from typing import Dict, Optional


class ProfitCaptureEngine:
    """
    CSS Profit Capture Engine (VWAP + Momentum Aware Upgrade)

    Backward compatible:
    - Works with old calls (price only)
    - Accepts optional intelligence inputs

    New capabilities:
    - VWAP-aware exits
    - Momentum + velocity-based decisions
    - Runner mode (let winners run intelligently)
    - Adaptive profit lock
    """

    def __init__(
        self,
        take_profit_bps: float,
        stop_loss_bps: float,
        trail_trigger_bps: float = 40.0,
        locked_profit_bps: float = 15.0,
    ):
        self.take_profit = take_profit_bps / 10000.0
        self.stop_loss = stop_loss_bps / 10000.0
        self.trail_trigger = trail_trigger_bps / 10000.0
        self.locked_profit = locked_profit_bps / 10000.0

    def evaluate(
        self,
        entry_price: float,
        current_price: float,
        peak_price: float,
        vwap: Optional[float] = None,
        momentum: float = 0.0,
        velocity: float = 0.0,
        mean_reversion_score: float = 0.0,
        regime: str = "NEUTRAL",
    ) -> Dict:

        if entry_price <= 0:
            return {"action": "HOLD", "pnl_pct": 0.0, "reason": "invalid entry"}

        change = (current_price - entry_price) / entry_price
        peak_change = (peak_price - entry_price) / entry_price

        # -------------------------
        # HARD STOP LOSS
        # -------------------------
        if change <= -self.stop_loss:
            return {
                "action": "STOP_LOSS",
                "pnl_pct": change,
                "reason": "hard stop loss hit",
            }

        # -------------------------
        # HARD TAKE PROFIT (SAFETY CAP)
        # -------------------------
        if change >= self.take_profit:
            return {
                "action": "TAKE_PROFIT",
                "pnl_pct": change,
                "reason": "hard take profit cap",
            }

        # -------------------------
        # VWAP CONTEXT
        # -------------------------
        vwap_dev = 0.0
        if vwap and vwap > 0:
            vwap_dev = (current_price - vwap) / vwap

        # -------------------------
        # RUNNER MODE (STRONG TREND)
        # -------------------------
        runner_mode = False

        if regime in ["TREND", "BREAKOUT"]:
            if abs(momentum) > 0.002 and velocity >= 0:
                runner_mode = True

        # -------------------------
        # VWAP REVERSION EXIT
        # -------------------------
        if vwap and abs(vwap_dev) < 0.0015:
            if mean_reversion_score > 0.5:
                return {
                    "action": "EXIT_LOCK_PROFIT",
                    "pnl_pct": change,
                    "reason": "vwap reversion completed",
                }

        # -------------------------
        # MOMENTUM DECAY EXIT
        # -------------------------
        if change > 0:
            if momentum < 0.001 and velocity < 0:
                return {
                    "action": "EXIT_LOCK_PROFIT",
                    "pnl_pct": change,
                    "reason": "momentum collapse",
                }

        # -------------------------
        # VELOCITY REVERSAL EXIT
        # -------------------------
        if change > 0:
            if velocity < -0.001:
                return {
                    "action": "EXIT_LOCK_PROFIT",
                    "pnl_pct": change,
                    "reason": "velocity reversal",
                }

        # -------------------------
        # TRAILING LOGIC (ENHANCED)
        # -------------------------
        if peak_change >= self.trail_trigger:

            lock_level = entry_price * (1 + self.locked_profit)

            # adaptive tightening if momentum weakens
            if momentum < 0:
                lock_level = entry_price * (1 + self.locked_profit * 0.7)

            if current_price < lock_level:
                return {
                    "action": "EXIT_LOCK_PROFIT",
                    "pnl_pct": change,
                    "reason": "trailing profit lock triggered",
                }

            # if strong runner → extend
            if runner_mode:
                return {
                    "action": "HOLD",
                    "pnl_pct": change,
                    "reason": "runner mode active",
                }

            return {
                "action": "HOLD",
                "pnl_pct": change,
                "reason": "trailing active",
            }

        # -------------------------
        # DEFAULT HOLD
        # -------------------------
        return {
            "action": "HOLD",
            "pnl_pct": change,
            "reason": "within normal range",
        }