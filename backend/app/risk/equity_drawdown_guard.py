"""
Equity Drawdown Guard – REA Capital Trading Engine
--------------------------------------------------

Purpose:
- Protect total capital from catastrophic erosion.
- Block trading if equity drawdown exceeds configured threshold.
- Fail-closed: missing equity data => BLOCK.

"""

from dataclasses import dataclass
from backend.runtime.capital_state import evaluate_drawdown_state


@dataclass(frozen=True)
class EquityDrawdownPolicy:
    max_drawdown_pct: float = 25.0  # 25% cap


def evaluate_equity_drawdown(
    current_equity: float | None,
    peak_equity: float | None,
    policy: EquityDrawdownPolicy,
    *,
    capital_state: str = "CAPITAL_READY",
    drawdown_reason: str = "",
) -> dict:
    return evaluate_drawdown_state(
        current_equity=current_equity,
        peak_equity=peak_equity,
        max_drawdown_pct=policy.max_drawdown_pct,
        capital_state=capital_state,
        drawdown_reason=drawdown_reason,
    )
