"""
Adaptive Portfolio Cap Scaler
Capital Strata Systems / REA Capital Trading Engine

Purpose:
- Dynamically scale allowable risk + max position notional
  based on drawdown, regime, and cooldown status.
- Deterministic, explainable, governance-friendly.

Fail-closed:
- If inputs are invalid, returns a conservative cap.

This module does NOT place trades. It computes limits used by RiskGovernor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass(frozen=True)
class CapDecision:
    ok: bool
    equity: float
    equity_peak: float
    drawdown_pct: float

    # Caps
    risk_budget_pct: float          # fraction of equity allowed at risk (e.g., 0.005 = 0.5%)
    max_position_notional_pct: float  # fraction of equity allowed as notional exposure

    # Metadata
    regime: str
    cooldown_active: bool
    reasons: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "equity": self.equity,
            "equity_peak": self.equity_peak,
            "drawdown_pct": self.drawdown_pct,
            "risk_budget_pct": self.risk_budget_pct,
            "max_position_notional_pct": self.max_position_notional_pct,
            "regime": self.regime,
            "cooldown_active": self.cooldown_active,
            "reasons": self.reasons,
        }


class AdaptiveCapScaler:
    """
    Deterministic cap scaler. You can tune bands later.

    Regimes (string):
      - "normal"  : default
      - "cautious": e.g., high vol / news / low-liquidity session
      - "aggressive": optional, only if governance allows

    Drawdown bands:
      0–3%    : normal sizing
      3–7%    : reduced
      7–12%   : tight
      >12%    : survival mode
    """

    # Base caps (normal regime, no drawdown)
    BASE_RISK_BUDGET_PCT = 0.005          # 0.50% of equity "risk budget"
    BASE_MAX_NOTIONAL_PCT = 0.20          # 20% notional exposure cap

    # Floors (never exceed conservatism below these)
    FLOOR_RISK_BUDGET_PCT = 0.0015        # 0.15%
    FLOOR_MAX_NOTIONAL_PCT = 0.06         # 6%

    # Cooldown multipliers
    COOLDOWN_RISK_MULT = 0.60
    COOLDOWN_NOTIONAL_MULT = 0.60

    # Regime multipliers
    REGIME_MULTIPLIERS = {
        "normal": (1.00, 1.00),
        "cautious": (0.75, 0.75),
        "aggressive": (1.10, 1.10),
    }

    def compute(
        self,
        *,
        equity: float,
        equity_peak: float,
        regime: str = "normal",
        cooldown_active: bool = False,
    ) -> CapDecision:
        reasons: List[str] = []

        # -----------------------
        # Validate inputs
        # -----------------------
        if equity <= 0 or equity_peak <= 0:
            return CapDecision(
                ok=False,
                equity=equity,
                equity_peak=equity_peak,
                drawdown_pct=1.0,
                risk_budget_pct=self.FLOOR_RISK_BUDGET_PCT,
                max_position_notional_pct=self.FLOOR_MAX_NOTIONAL_PCT,
                regime="normal",
                cooldown_active=cooldown_active,
                reasons=["invalid_equity_inputs_fail_closed"],
            )

        if equity_peak < equity:
            equity_peak = equity
            reasons.append("equity_peak_raised_to_equity")

        # -----------------------
        # Drawdown
        # -----------------------
        drawdown_pct = max(0.0, (equity_peak - equity) / equity_peak)

        # -----------------------
        # Base caps -> drawdown scaling
        # -----------------------
        rb = self.BASE_RISK_BUDGET_PCT
        mn = self.BASE_MAX_NOTIONAL_PCT

        if drawdown_pct < 0.03:
            reasons.append("drawdown_band_0_3")
            dd_mult = 1.00
        elif drawdown_pct < 0.07:
            reasons.append("drawdown_band_3_7")
            dd_mult = 0.75
        elif drawdown_pct < 0.12:
            reasons.append("drawdown_band_7_12")
            dd_mult = 0.55
        else:
            reasons.append("drawdown_band_gt_12_survival")
            dd_mult = 0.40

        rb *= dd_mult
        mn *= dd_mult

        # -----------------------
        # Regime
        # -----------------------
        if regime not in self.REGIME_MULTIPLIERS:
            regime = "normal"
            reasons.append("unknown_regime_defaulted_normal")

        r_mult, n_mult = self.REGIME_MULTIPLIERS[regime]
        rb *= r_mult
        mn *= n_mult
        reasons.append(f"regime_{regime}")

        # -----------------------
        # Cooldown
        # -----------------------
        if cooldown_active:
            rb *= self.COOLDOWN_RISK_MULT
            mn *= self.COOLDOWN_NOTIONAL_MULT
            reasons.append("cooldown_active_scaled_down")

        # -----------------------
        # Floors
        # -----------------------
        rb = max(self.FLOOR_RISK_BUDGET_PCT, rb)
        mn = max(self.FLOOR_MAX_NOTIONAL_PCT, mn)

        return CapDecision(
            ok=True,
            equity=equity,
            equity_peak=equity_peak,
            drawdown_pct=drawdown_pct,
            risk_budget_pct=rb,
            max_position_notional_pct=mn,
            regime=regime,
            cooldown_active=cooldown_active,
            reasons=reasons,
        )
