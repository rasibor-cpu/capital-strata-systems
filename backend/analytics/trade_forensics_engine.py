from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


class TradeForensicsEngineError(RuntimeError):
    """Fail-closed exception for trade forensics."""


class TradeForensicsEngine:
    def explain_trade(self, trade: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(trade, Mapping):
            raise TradeForensicsEngineError("trade must be a mapping")

        trade_id = str(trade.get("trade_id") or "").strip()
        if not trade_id:
            raise TradeForensicsEngineError("trade_id must be non-empty")

        strategy = str(trade.get("strategy_id") or trade.get("strategy") or "UNKNOWN").strip() or "UNKNOWN"
        market_regime = str(trade.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"
        confidence = self._float(trade.get("confidence", trade.get("decision_confidence", 0.0)))
        quality_score = self._float(trade.get("quality_score", 0.0))
        position_size = self._float(trade.get("position_size", trade.get("recommended_position_size", 0.0)))
        capital_allocation = self._float(trade.get("capital_allocation", trade.get("allocation_amount", 0.0)))
        holding_time_seconds = self._holding_seconds(trade)
        pnl = self._float(trade.get("realized_pnl", trade.get("pnl", 0.0)))
        expected_pnl = self._float(trade.get("expected_pnl", trade.get("forecast_pnl", pnl)))
        entry_reason = str(trade.get("entry_reason") or trade.get("signal_reason") or f"{strategy} aligned with {market_regime}").strip()
        exit_reason = str(trade.get("exit_reason") or trade.get("close_reason") or ("take_profit" if pnl >= 0.0 else "stop_loss")).strip()

        decision_optimal = pnl >= expected_pnl
        trade_quality = self._quality_label(quality_score)

        return {
            "trade_id": trade_id,
            "entry_reason": entry_reason,
            "exit_reason": exit_reason,
            "strategy": strategy,
            "market_regime": market_regime,
            "confidence": round(confidence, 8),
            "trade_quality": trade_quality,
            "trade_quality_score": round(quality_score, 8),
            "position_size": round(position_size, 8),
            "capital_allocation": round(capital_allocation, 8),
            "holding_time_seconds": round(holding_time_seconds, 8),
            "pnl": round(pnl, 8),
            "expected_pnl": round(expected_pnl, 8),
            "decision_optimal": decision_optimal,
            "optimality_reason": "expected_or_better" if decision_optimal else "below_expected_outcome",
        }

    def explain_trades(self, trades: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        rows = trades if isinstance(trades, list) else []
        explanations = [self.explain_trade(trade) for trade in rows]
        return sorted(explanations, key=lambda item: item["trade_id"])

    @staticmethod
    def _holding_seconds(trade: Mapping[str, Any]) -> float:
        for key in ("holding_time_seconds", "holding_duration_seconds", "holding_duration_minutes"):
            if key in trade:
                value = trade.get(key)
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    numeric = 0.0
                if key.endswith("minutes"):
                    return numeric * 60.0
                return numeric
        return 0.0

    @staticmethod
    def _quality_label(score: float) -> str:
        if score >= 85.0:
            return "A"
        if score >= 70.0:
            return "B"
        if score >= 55.0:
            return "C"
        if score >= 40.0:
            return "D"
        return "E"

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
