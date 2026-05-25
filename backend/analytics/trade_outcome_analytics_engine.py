from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


class TradeOutcomeAnalyticsEngine:
    """Safe-mode, deterministic trade outcome analytics.

    This engine is read-only and computes summary metrics from closed/open trade
    payloads without mutating execution or risk pathways.
    """

    def build(self, trades: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        normalized = [self._normalize_trade(t) for t in (trades or [])]

        realized = [t for t in normalized if t["is_closed"]]
        unrealized = [t for t in normalized if not t["is_closed"]]

        winners = [t for t in realized if t["pnl"] > 0]
        losers = [t for t in realized if t["pnl"] < 0]

        gross_profit = sum(t["pnl"] for t in winners)
        gross_loss_abs = abs(sum(t["pnl"] for t in losers))

        trade_count = len(realized)
        win_rate = (len(winners) / trade_count) if trade_count else 0.0
        loss_rate = (len(losers) / trade_count) if trade_count else 0.0

        average_winner = (gross_profit / len(winners)) if winners else 0.0
        average_loser = (sum(t["pnl"] for t in losers) / len(losers)) if losers else 0.0
        expectancy = self._expectancy(win_rate, average_winner, loss_rate, average_loser)

        cumulative = 0.0
        max_equity = 0.0
        max_drawdown = 0.0
        for trade in realized:
            cumulative += trade["pnl"]
            max_equity = max(max_equity, cumulative)
            drawdown = max_equity - cumulative
            max_drawdown = max(max_drawdown, drawdown)

        duration_minutes = [t["duration_minutes"] for t in realized if t["duration_minutes"] >= 0.0]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "deterministic": True,
            "trade_count": trade_count,
            "winner_count": len(winners),
            "loser_count": len(losers),
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "average_winner": average_winner,
            "average_loser": average_loser,
            "expectancy": expectancy,
            "gross_profit": gross_profit,
            "gross_loss_abs": gross_loss_abs,
            "profit_factor": (gross_profit / gross_loss_abs) if gross_loss_abs > 0 else 0.0,
            "max_drawdown": max_drawdown,
            "duration": {
                "average_minutes": (sum(duration_minutes) / len(duration_minutes)) if duration_minutes else 0.0,
                "median_minutes": self._median(duration_minutes),
                "max_minutes": max(duration_minutes) if duration_minutes else 0.0,
            },
            "realized_vs_unrealized": {
                "closed_trade_count": len(realized),
                "open_trade_count": len(unrealized),
                "realized_pnl": sum(t["pnl"] for t in realized),
                "unrealized_pnl": sum(t["pnl"] for t in unrealized),
            },
        }

    @staticmethod
    def _expectancy(win_rate: float, avg_winner: float, loss_rate: float, avg_loser: float) -> float:
        return (win_rate * avg_winner) + (loss_rate * avg_loser)

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    def _normalize_trade(self, trade: Mapping[str, Any]) -> dict[str, Any]:
        opened_at = self._to_dt(trade.get("opened_at"))
        closed_at = self._to_dt(trade.get("closed_at"))
        duration = (closed_at - opened_at).total_seconds() / 60.0 if (opened_at and closed_at) else -1.0
        return {
            "pnl": float(trade.get("pnl", 0.0)),
            "is_closed": bool(trade.get("is_closed", trade.get("closed_at") is not None)),
            "duration_minutes": duration,
        }

    @staticmethod
    def _to_dt(raw: Any) -> datetime | None:
        if isinstance(raw, datetime):
            return raw
        if isinstance(raw, str) and raw:
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None
