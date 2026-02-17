"""
Risk Telemetry – Institutional Risk State Monitor
Capital Strata Systems

Purpose:
- Track rolling equity + peak
- Compute drawdown %
- Track effective risk %
- Detect kill-switch conditions
- Emit structured telemetry snapshot

Kill-switch:
- Hard stop at 20% peak drawdown
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


# ============================================================
# Telemetry State
# ============================================================

@dataclass
class RiskTelemetrySnapshot:
    equity: float
    equity_peak: float
    drawdown_pct: float
    effective_risk_pct: float
    compounding_applied: bool
    regime_persistence: Optional[float]
    kill_switch_triggered: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "equity": self.equity,
            "equity_peak": self.equity_peak,
            "drawdown_pct": self.drawdown_pct,
            "effective_risk_pct": self.effective_risk_pct,
            "compounding_applied": self.compounding_applied,
            "regime_persistence": self.regime_persistence,
            "kill_switch_triggered": self.kill_switch_triggered,
        }


# ============================================================
# Telemetry Engine
# ============================================================

class RiskTelemetry:

    HARD_DRAWDOWN_LIMIT = 0.20  # 20%

    def __init__(self) -> None:
        self.equity: Optional[float] = None
        self.equity_peak: Optional[float] = None
        self.kill_switch_triggered: bool = False

    # --------------------------------------------------------
    # Equity Updates
    # --------------------------------------------------------

    def update_equity(self, equity: float) -> None:
        equity = float(equity)

        if self.equity_peak is None:
            self.equity_peak = equity
        else:
            self.equity_peak = max(self.equity_peak, equity)

        self.equity = equity

        self._check_kill_switch()

    # --------------------------------------------------------
    # Drawdown
    # --------------------------------------------------------

    def _compute_drawdown_pct(self) -> float:
        if self.equity is None or self.equity_peak is None:
            return 0.0

        if self.equity_peak == 0:
            return 0.0

        return (self.equity_peak - self.equity) / self.equity_peak

    # --------------------------------------------------------
    # Kill Switch
    # --------------------------------------------------------

    def _check_kill_switch(self) -> None:
        dd = self._compute_drawdown_pct()

        if dd >= self.HARD_DRAWDOWN_LIMIT:
            self.kill_switch_triggered = True

    # --------------------------------------------------------
    # Public Snapshot
    # --------------------------------------------------------

    def snapshot(
        self,
        *,
        effective_risk_pct: float,
        compounding_applied: bool,
        regime_persistence: Optional[float],
    ) -> RiskTelemetrySnapshot:

        drawdown_pct = self._compute_drawdown_pct()

        return RiskTelemetrySnapshot(
            equity=self.equity or 0.0,
            equity_peak=self.equity_peak or 0.0,
            drawdown_pct=drawdown_pct,
            effective_risk_pct=float(effective_risk_pct),
            compounding_applied=bool(compounding_applied),
            regime_persistence=regime_persistence,
            kill_switch_triggered=self.kill_switch_triggered,
        )
