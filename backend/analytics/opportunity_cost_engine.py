from __future__ import annotations

from typing import Any, Mapping


class OpportunityCostEngineError(RuntimeError):
    """Fail-closed exception for opportunity cost analysis."""


class OpportunityCostEngine:
    def analyze_rejected_trades(self, rejected_trades: list[Mapping[str, Any]] | None) -> dict[str, Any]:
        rows = rejected_trades if isinstance(rejected_trades, list) else []
        if not rows:
            return {"opportunity_costs": [], "summary": {"rejected_trade_count": 0, "missed_opportunity_total": 0.0}}

        opportunity_costs = [self._analyze_trade(trade) for trade in rows]
        opportunity_costs.sort(key=lambda item: (item["trade_id"], item["rejection_reason"]))
        missed_total = sum(item["missed_opportunity"] for item in opportunity_costs)
        return {
            "opportunity_costs": opportunity_costs,
            "summary": {
                "rejected_trade_count": len(opportunity_costs),
                "missed_opportunity_total": round(missed_total, 8),
                "average_expected_profit": round(missed_total / len(opportunity_costs), 8) if opportunity_costs else 0.0,
            },
        }

    def _analyze_trade(self, trade: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(trade, Mapping):
            raise OpportunityCostEngineError("rejected trade must be a mapping")

        trade_id = str(trade.get("trade_id") or "").strip()
        if not trade_id:
            raise OpportunityCostEngineError("trade_id must be non-empty")
        rejection_reason = str(trade.get("rejection_reason") or trade.get("reason") or "UNKNOWN").strip() or "UNKNOWN"
        confidence = self._float(trade.get("confidence", trade.get("decision_confidence", 0.0)))
        expected_profit = self._float(trade.get("expected_pnl", trade.get("expected_profit", trade.get("forecast_pnl", 0.0))))
        realized_pnl = self._float(trade.get("realized_pnl", trade.get("pnl", expected_profit)))
        would_have_won = realized_pnl > 0.0
        missed_opportunity = max(0.0, expected_profit)

        if expected_profit <= 0.0:
            threshold_implication = "raise_acceptance_threshold"
        elif confidence < 0.5:
            threshold_implication = "relax_acceptance_threshold"
        elif "regime" in rejection_reason.lower():
            threshold_implication = "reduce_exposure_in_weak_regime"
        else:
            threshold_implication = "tighten_exit_confidence"

        return {
            "trade_id": trade_id,
            "rejection_reason": rejection_reason,
            "would_have_won": would_have_won,
            "expected_profit": round(expected_profit, 8),
            "missed_opportunity": round(missed_opportunity, 8),
            "confidence": round(confidence, 8),
            "threshold_implication": threshold_implication,
        }

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
