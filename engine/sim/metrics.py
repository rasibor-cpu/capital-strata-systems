"""
Simulation Metrics (Read-Only)
------------------------------
Computes trading performance metrics from PaperSimulator state.

Design:
- Pure functions / read-only
- Deterministic
- No external IO

Metrics:
- Win rate
- Avg win / avg loss
- Payoff ratio
- Expectancy
- Equity curve (simple)
- Drawdown (already tracked in simulator, recomputed for curve validation)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class MetricsReport:
    trades: int
    wins: int
    losses: int
    win_rate: float
    avg_win: float
    avg_loss: float
    payoff_ratio: float
    expectancy: float
    max_drawdown_pct: float
    equity_curve: List[float]


def _safe_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0.0


def compute_metrics(
    *,
    starting_equity: float,
    trade_pnls: List[float],
) -> MetricsReport:
    trades = len(trade_pnls)
    wins_list = [p for p in trade_pnls if p > 0]
    losses_list = [p for p in trade_pnls if p <= 0]

    wins = len(wins_list)
    losses = len(losses_list)
    win_rate = _safe_div(wins, trades) if trades > 0 else 0.0

    avg_win = sum(wins_list) / wins if wins > 0 else 0.0
    avg_loss = sum(losses_list) / losses if losses > 0 else 0.0  # negative or 0

    payoff_ratio = _safe_div(avg_win, abs(avg_loss)) if avg_loss < 0 else (avg_win if avg_win > 0 else 0.0)

    # Expectancy per trade: (P(win)*avg_win) + (P(loss)*avg_loss)
    p_loss = 1.0 - win_rate if trades > 0 else 0.0
    expectancy = (win_rate * avg_win) + (p_loss * avg_loss)

    # Equity curve + max drawdown
    equity_curve: List[float] = [starting_equity]
    eq = starting_equity
    peak = starting_equity
    max_dd = 0.0
    for pnl in trade_pnls:
        eq += pnl
        equity_curve.append(eq)
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    return MetricsReport(
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 4),
        avg_win=round(avg_win, 4),
        avg_loss=round(avg_loss, 4),
        payoff_ratio=round(payoff_ratio, 4),
        expectancy=round(expectancy, 4),
        max_drawdown_pct=round(max_dd, 4),
        equity_curve=[round(x, 4) for x in equity_curve],
    )


def metrics_from_simulator(sim) -> MetricsReport:
    """
    Adapter for PaperSimulator without importing it here (keeps this module clean).
    Expects:
      sim.state.starting_equity
      sim.state.trades with pnl
    """
    pnls = [t.pnl for t in getattr(sim.state, "trades", [])]
    return compute_metrics(starting_equity=sim.state.starting_equity, trade_pnls=pnls)


# Safety invariant
if __name__ == "__main__":
    raise RuntimeError("metrics.py is a library module only and must not be executed directly.")
"""
Simulation Metrics (Read-Only)
------------------------------
Computes trading performance metrics from PaperSimulator state.

Design:
- Pure functions / read-only
- Deterministic
- No external IO

Metrics:
- Win rate
- Avg win / avg loss
- Payoff ratio
- Expectancy
- Equity curve (simple)
- Drawdown (already tracked in simulator, recomputed for curve validation)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class MetricsReport:
    trades: int
    wins: int
    losses: int
    win_rate: float
    avg_win: float
    avg_loss: float
    payoff_ratio: float
    expectancy: float
    max_drawdown_pct: float
    equity_curve: List[float]


def _safe_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0.0


def compute_metrics(
    *,
    starting_equity: float,
    trade_pnls: List[float],
) -> MetricsReport:
    trades = len(trade_pnls)
    wins_list = [p for p in trade_pnls if p > 0]
    losses_list = [p for p in trade_pnls if p <= 0]

    wins = len(wins_list)
    losses = len(losses_list)
    win_rate = _safe_div(wins, trades) if trades > 0 else 0.0

    avg_win = sum(wins_list) / wins if wins > 0 else 0.0
    avg_loss = sum(losses_list) / losses if losses > 0 else 0.0  # negative or 0

    payoff_ratio = _safe_div(avg_win, abs(avg_loss)) if avg_loss < 0 else (avg_win if avg_win > 0 else 0.0)

    # Expectancy per trade: (P(win)*avg_win) + (P(loss)*avg_loss)
    p_loss = 1.0 - win_rate if trades > 0 else 0.0
    expectancy = (win_rate * avg_win) + (p_loss * avg_loss)

    # Equity curve + max drawdown
    equity_curve: List[float] = [starting_equity]
    eq = starting_equity
    peak = starting_equity
    max_dd = 0.0
    for pnl in trade_pnls:
        eq += pnl
        equity_curve.append(eq)
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    return MetricsReport(
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 4),
        avg_win=round(avg_win, 4),
        avg_loss=round(avg_loss, 4),
        payoff_ratio=round(payoff_ratio, 4),
        expectancy=round(expectancy, 4),
        max_drawdown_pct=round(max_dd, 4),
        equity_curve=[round(x, 4) for x in equity_curve],
    )


def metrics_from_simulator(sim) -> MetricsReport:
    """
    Adapter for PaperSimulator without importing it here (keeps this module clean).
    Expects:
      sim.state.starting_equity
      sim.state.trades with pnl
    """
    pnls = [t.pnl for t in getattr(sim.state, "trades", [])]
    return compute_metrics(starting_equity=sim.state.starting_equity, trade_pnls=pnls)


# Safety invariant
if __name__ == "__main__":
    raise RuntimeError("metrics.py is a library module only and must not be executed directly.")
