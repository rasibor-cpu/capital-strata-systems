from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class TradeOutcome:
    symbol: str
    asset_class: str = "unknown"
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None


class TradeOutcomeAnalyticsEngine:
    """
    Safe-mode, read-only trade outcome analytics engine.

    This engine does not make execution, routing, sizing, or governance decisions.
    It only summarizes supplied trade/position-like records for dashboard visibility.
    """

    def summarize(self, trades: Optional[Iterable[Any]] = None) -> Dict[str, Any]:
        normalized = [self._normalize_trade(t) for t in (trades or [])]
        realized = [t.realized_pnl for t in normalized]
        winners = [p for p in realized if p > 0]
        losers = [p for p in realized if p < 0]

        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        expectancy = sum(realized) / len(realized) if realized else 0.0
        win_rate = len(winners) / len(realized) if realized else 0.0

        payload = {
            "timestamp": self._now(),
            "trade_count": len(normalized),
            "expectancy": round(expectancy, 6),
            "profit_factor": round(profit_factor, 6),
            "win_rate": round(win_rate, 6),
            "average_winner": round(sum(winners) / len(winners), 6) if winners else 0.0,
            "average_loser": round(sum(losers) / len(losers), 6) if losers else 0.0,
            "gross_profit": round(gross_profit, 6),
            "gross_loss": round(gross_loss, 6),
            "max_drawdown": round(self._max_drawdown(realized), 6),
            "average_duration_seconds": round(self._average_duration_seconds(normalized), 6),
            "realized_total": round(sum(realized), 6),
            "unrealized_total": round(sum(t.unrealized_pnl for t in normalized), 6),
            "mode": "safe_read_only",
        }
        return payload

    def _normalize_trade(self, trade: Any) -> TradeOutcome:
        if isinstance(trade, TradeOutcome):
            return trade
        if isinstance(trade, dict):
            return TradeOutcome(
                symbol=str(trade.get("symbol", "UNKNOWN")),
                asset_class=str(trade.get("asset_class", trade.get("assetClass", "unknown"))),
                realized_pnl=float(trade.get("realized_pnl", trade.get("realizedPnL", trade.get("pnl", 0.0))) or 0.0),
                unrealized_pnl=float(trade.get("unrealized_pnl", trade.get("unrealizedPnL", 0.0)) or 0.0),
                opened_at=trade.get("opened_at") or trade.get("openedAt"),
                closed_at=trade.get("closed_at") or trade.get("closedAt"),
            )
        return TradeOutcome(
            symbol=str(getattr(trade, "symbol", "UNKNOWN")),
            asset_class=str(getattr(trade, "asset_class", "unknown")),
            realized_pnl=float(getattr(trade, "realized_pnl", getattr(trade, "pnl", 0.0)) or 0.0),
            unrealized_pnl=float(getattr(trade, "unrealized_pnl", 0.0) or 0.0),
            opened_at=getattr(trade, "opened_at", None),
            closed_at=getattr(trade, "closed_at", None),
        )

    def _max_drawdown(self, pnl_series: List[float]) -> float:
        peak = 0.0
        equity = 0.0
        max_dd = 0.0
        for pnl in pnl_series:
            equity += pnl
            peak = max(peak, equity)
            max_dd = min(max_dd, equity - peak)
        return abs(max_dd)

    def _average_duration_seconds(self, trades: List[TradeOutcome]) -> float:
        durations: List[float] = []
        for trade in trades:
            if not trade.opened_at or not trade.closed_at:
                continue
            try:
                start = datetime.fromisoformat(str(trade.opened_at).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(trade.closed_at).replace("Z", "+00:00"))
                durations.append(max((end - start).total_seconds(), 0.0))
            except Exception:
                continue
        return sum(durations) / len(durations) if durations else 0.0

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_dict(self, trade: TradeOutcome) -> Dict[str, Any]:
        return asdict(trade)