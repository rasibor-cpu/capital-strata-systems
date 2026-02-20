"""
PerformanceMetrics – Institutional Trade Distribution Analytics
Capital Strata Systems (CSS)

Purpose:
- Measure trade quality, not just profit
- Instrument-level expectancy analysis
- Win rate, payoff ratio, Sharpe-lite proxy
- Risk-adjusted capital efficiency metrics

This does NOT mutate state.
Pure analytics layer.
"""

from __future__ import annotations

from typing import Dict, Any, List
import math


class PerformanceMetrics:

    def __init__(self, pnl_tracker) -> None:
        self.tracker = pnl_tracker

    # ------------------------------------------------------------
    # Core Instrument Metrics
    # ------------------------------------------------------------

    def instrument_metrics(self) -> Dict[str, Dict[str, float]]:
        results: Dict[str, Dict[str, float]] = {}

        for instrument, ledger in self.tracker.instrument_ledgers.items():

            trades = ledger.trades
            if trades == 0:
                continue

            # Extract trade history
            realized = [
                entry.realized_pnl
                for entry in self.tracker.journal
                if entry.instrument == instrument
            ]

            wins = [p for p in realized if p > 0]
            losses = [p for p in realized if p < 0]

            win_rate = len(wins) / trades if trades > 0 else 0.0
            avg_win = sum(wins) / len(wins) if wins else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0

            payoff_ratio = (
                abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")
            )

            expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

            pnl_vol = self._std_dev(realized)
            sharpe_like = expectancy / pnl_vol if pnl_vol > 0 else 0.0

            results[instrument] = {
                "trades": trades,
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "payoff_ratio": payoff_ratio,
                "expectancy": expectancy,
                "pnl_volatility": pnl_vol,
                "sharpe_like": sharpe_like,
            }

        return results

    # ------------------------------------------------------------
    # Portfolio Metrics
    # ------------------------------------------------------------

    def portfolio_metrics(self) -> Dict[str, float]:

        realized = [entry.realized_pnl for entry in self.tracker.journal]

        if not realized:
            return {}

        total_trades = len(realized)
        wins = [p for p in realized if p > 0]
        losses = [p for p in realized if p < 0]

        win_rate = len(wins) / total_trades
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

        pnl_vol = self._std_dev(realized)
        sharpe_like = expectancy / pnl_vol if pnl_vol > 0 else 0.0

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "pnl_volatility": pnl_vol,
            "sharpe_like": sharpe_like,
        }

    # ------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------

    def _std_dev(self, data: List[float]) -> float:
        if len(data) < 2:
            return 0.0

        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / (len(data) - 1)
        return math.sqrt(variance)
