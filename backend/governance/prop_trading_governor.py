
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class PropTradingEvaluationState:
    """
    Tracks funded-account style evaluation state.

    Phase 64A:
    - additive only
    - no broker execution changes
    - governance layer only
    - fail-closed behavior
    """

    trading_day: str = ""
    daily_loss_limit: float = 0.0
    max_drawdown_limit: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    open_positions: int = 0
    violations: List[str] = field(default_factory=list)

    @property
    def total_pnl(self) -> float:
        return float(self.realized_pnl + self.unrealized_pnl)

    @property
    def drawdown(self) -> float:
        return float(self.peak_equity - self.current_equity)

    @property
    def daily_loss_breached(self) -> bool:
        return self.total_pnl <= (-1.0 * abs(self.daily_loss_limit))

    @property
    def max_drawdown_breached(self) -> bool:
        return self.drawdown >= abs(self.max_drawdown_limit)


class PropTradingGovernor:
    """
    Phase 64A governance foundation.

    Responsibilities:
    - funded-account evaluation checks
    - prop-firm style rule enforcement
    - daily loss governance
    - max drawdown governance
    - exposure gating
    - fail-closed approval model

    Explicit NON-responsibilities:
    - no order execution
    - no broker routing
    - no dashboard rendering
    - no mutation of execution engine
    """

    def __init__(
        self,
        enabled: bool = True,
        max_open_positions: int = 10,
        enforce_daily_loss_limit: bool = True,
        enforce_drawdown_limit: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.max_open_positions = int(max_open_positions)
        self.enforce_daily_loss_limit = bool(
            enforce_daily_loss_limit
        )
        self.enforce_drawdown_limit = bool(
            enforce_drawdown_limit
        )

    def evaluate(
        self,
        state: PropTradingEvaluationState,
    ) -> Dict[str, Any]:
        """
        Fail-closed governance evaluation.
        """

        if not self.enabled:
            return {
                "allowed": True,
                "blocked": False,
                "reasons": [],
                "governor": "disabled",
            }

        reasons: List[str] = []

        if (
            self.enforce_daily_loss_limit
            and state.daily_loss_breached
        ):
            reasons.append(
                "daily_loss_limit_breached"
            )

        if (
            self.enforce_drawdown_limit
            and state.max_drawdown_breached
        ):
            reasons.append(
                "max_drawdown_limit_breached"
            )

        if (
            int(state.open_positions)
            > int(self.max_open_positions)
        ):
            reasons.append(
                "max_open_positions_exceeded"
            )

        if state.violations:
            reasons.extend(
                [
                    str(v)
                    for v in state.violations
                ]
            )

        blocked = len(reasons) > 0

        return {
            "allowed": not blocked,
            "blocked": blocked,
            "reasons": reasons,
            "daily_loss_breached": (
                state.daily_loss_breached
            ),
            "max_drawdown_breached": (
                state.max_drawdown_breached
            ),
            "drawdown": state.drawdown,
            "total_pnl": state.total_pnl,
            "open_positions": int(
                state.open_positions
            ),
            "governor": (
                "prop_trading_compliance"
            ),
        }


def build_default_prop_state() -> PropTradingEvaluationState:
    """
    Safe default empty state.
    """

    return PropTradingEvaluationState(
        trading_day="",
        daily_loss_limit=2500.0,
        max_drawdown_limit=5000.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        peak_equity=100000.0,
        current_equity=100000.0,
        open_positions=0,
        violations=[],
    )


__all__ = [
    "PropTradingGovernor",
    "PropTradingEvaluationState",
    "build_default_prop_state",
]

