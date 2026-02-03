"""
REA Capital Trading Engine
Capital Risk Governor (Layer 4 – Loss Containment)

Constitutional Authority:
- Layer 4: Capital Risk
- This module has ABSOLUTE VETO power over exposure
- Strategy may REQUEST, Risk Governor DECIDES

Doctrine:
- Survival precedes profitability
- Loss must be bounded BEFORE execution
- Default state = NO TRADE
"""

from dataclasses import dataclass
from typing import Optional, Dict
import time


# -----------------------------
# Risk Decision (Immutable)
# -----------------------------
@dataclass(frozen=True)
class RiskDecision:
    allow: bool
    approved_size: float
    max_loss: float
    reason: str
    timestamp: float


# -----------------------------
# Risk Context Snapshot
# -----------------------------
@dataclass
class RiskContext:
    equity: float
    volatility: float
    session_drawdown: float
    daily_drawdown: float
    correlated_exposure: float


# -----------------------------
# Capital Risk Governor
# -----------------------------
class RiskGovernor:
    """
    RiskGovernor enforces capital preservation.
    It does not optimize returns.
    It only answers: can we survive if this is wrong?
    """

    def __init__(
        self,
        max_risk_fraction: float,
        max_session_drawdown: float,
        max_daily_drawdown: float,
        min_volatility: float = 1e-8,
    ):
        if max_risk_fraction <= 0:
            raise ValueError("max_risk_fraction must be positive")

        self.max_risk_fraction = max_risk_fraction
        self.max_session_drawdown = max_session_drawdown
        self.max_daily_drawdown = max_daily_drawdown
        self.min_volatility = min_volatility

    # -------------------------
    # Core Evaluation
    # -------------------------
    def evaluate(
        self,
        requested_size: float,
        stop_distance: Optional[float],
        ctx: RiskContext,
    ) -> RiskDecision:
        ts = time.time()

        # ---- Hard Fails ----
        if ctx.equity <= 0:
            return self._block("Invalid equity", ts)

        if requested_size <= 0:
            return self._block("Requested size invalid", ts)

        if stop_distance is None or stop_distance <= 0:
            return self._block("Undefined maximum loss (stop distance)", ts)

        # ---- Drawdown Gates ----
        if ctx.session_drawdown >= self.max_session_drawdown:
            return self._block("Session drawdown limit breached", ts)

        if ctx.daily_drawdown >= self.max_daily_drawdown:
            return self._block("Daily drawdown limit breached", ts)

        # ---- Risk Budget ----
        max_risk_amount = ctx.equity * self.max_risk_fraction

        # ---- Volatility Scaling ----
        effective_vol = max(ctx.volatility, self.min_volatility)
        volatility_scale = 1.0 / effective_vol

        # ---- Size Based on Risk ----
        raw_size = max_risk_amount / stop_distance
        scaled_size = raw_size * volatility_scale

        # ---- Correlation Clamp ----
        net_size = max(0.0, scaled_size - ctx.correlated_exposure)

        if net_size <= 0:
            return self._block("Correlated exposure cap reached", ts)

        approved_size = min(net_size, requested_size)

        max_loss = approved_size * stop_distance

        if max_loss > max_risk_amount:
            return self._block("Risk exceeds maximum allowed", ts)

        return RiskDecision(
            allow=True,
            approved_size=approved_size,
            max_loss=max_loss,
            reason="Risk approved within limits",
            timestamp=ts,
        )

    # -------------------------
    # Internal Helper
    # -------------------------
    def _block(self, reason: str, ts: float) -> RiskDecision:
        return RiskDecision(
            allow=False,
            approved_size=0.0,
            max_loss=0.0,
            reason=reason,
            timestamp=ts,
        )


# -----------------------------
# Constitutional Assertion
# -----------------------------
if __name__ == "__main__":
    raise RuntimeError(
        "RiskGovernor is a control module only. "
        "It must be invoked by the execution pipeline."
    )
