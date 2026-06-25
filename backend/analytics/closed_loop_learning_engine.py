from __future__ import annotations

from typing import Any, Iterable, Mapping


class ClosedLoopLearningEngineError(RuntimeError):
    """Fail-closed exception for closed-loop learning operations."""


class ClosedLoopLearningEngine:
    """Routes completed trades into learning systems and emits auditable feedback summaries."""

    def __init__(
        self,
        *,
        learning_pipeline: Any | None = None,
        strategy_memory_repository: Any | None = None,
    ) -> None:
        self.learning_pipeline = learning_pipeline
        self.strategy_memory_repository = strategy_memory_repository

    def process_completed_trades(self, completed_trades: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        if completed_trades is None:
            raise ClosedLoopLearningEngineError("completed_trades must not be None")
        if not isinstance(completed_trades, Iterable):
            raise ClosedLoopLearningEngineError("completed_trades must be iterable")

        rows = list(completed_trades)
        if not rows:
            return {
                "updated_count": 0,
                "learning_writes": [],
                "quality_feedback_summary": {
                    "count": 0,
                    "average_quality_score": 0.0,
                    "recommendation_distribution": {},
                },
                "strategy_memory_summary": [],
            }

        updates: list[dict[str, Any]] = []
        recommendation_distribution: dict[str, int] = {}
        quality_scores: list[float] = []

        for raw in rows:
            trade = self._normalize_trade(raw)
            recommendation = str(trade.get("recommendation") or "UNKNOWN").strip().upper()
            recommendation_distribution[recommendation] = recommendation_distribution.get(recommendation, 0) + 1

            if "quality_score" in trade and trade.get("quality_score") is not None:
                quality_scores.append(self._safe_float(trade.get("quality_score"), "quality_score"))

            if self.learning_pipeline is not None:
                if not hasattr(self.learning_pipeline, "write_completed_trade"):
                    raise ClosedLoopLearningEngineError("learning_pipeline missing write_completed_trade")
                try:
                    updates.append(self.learning_pipeline.write_completed_trade(trade))
                except Exception as exc:
                    raise ClosedLoopLearningEngineError(str(exc)) from exc
            elif self.strategy_memory_repository is not None:
                if not hasattr(self.strategy_memory_repository, "persist_memory_record"):
                    raise ClosedLoopLearningEngineError("strategy_memory_repository missing persist_memory_record")
                updates.append(self.strategy_memory_repository.persist_memory_record(self._strategy_memory_record(trade)))
            else:
                raise ClosedLoopLearningEngineError("no learning target configured")

        strategy_memory_summary: list[dict[str, Any]] = []
        if self.strategy_memory_repository is not None and hasattr(self.strategy_memory_repository, "aggregate_strategy_performance"):
            try:
                strategy_memory_summary = list(self.strategy_memory_repository.aggregate_strategy_performance())
            except Exception as exc:
                raise ClosedLoopLearningEngineError(str(exc)) from exc

        feedback = {
            "count": len(rows),
            "average_quality_score": round(sum(quality_scores) / len(quality_scores), 8) if quality_scores else 0.0,
            "recommendation_distribution": {
                key: recommendation_distribution[key] for key in sorted(recommendation_distribution.keys())
            },
        }

        return {
            "updated_count": len(updates),
            "learning_writes": updates,
            "quality_feedback_summary": feedback,
            "strategy_memory_summary": strategy_memory_summary,
        }

    @staticmethod
    def _normalize_trade(payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise ClosedLoopLearningEngineError("each completed trade must be a mapping")

        required = {
            "trade_id",
            "timestamp_open",
            "timestamp_close",
            "symbol",
            "asset_class",
            "entry_price",
            "exit_price",
            "quantity",
            "realized_pnl",
            "holding_duration_seconds",
            "strategy_id",
            "broker",
            "session",
        }
        missing = [field for field in sorted(required) if field not in payload]
        if missing:
            raise ClosedLoopLearningEngineError(f"completed trade missing required fields: {', '.join(missing)}")

        normalized = dict(payload)
        normalized["trade_id"] = str(payload["trade_id"]).strip()
        normalized["symbol"] = str(payload["symbol"]).strip().upper()
        normalized["asset_class"] = str(payload["asset_class"]).strip().upper()
        normalized["strategy_id"] = str(payload["strategy_id"]).strip()
        normalized["broker"] = str(payload["broker"]).strip()
        normalized["session"] = str(payload["session"]).strip()
        normalized["market_regime"] = str(payload.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"

        for field in (
            "entry_price",
            "exit_price",
            "quantity",
            "realized_pnl",
            "holding_duration_seconds",
        ):
            normalized[field] = ClosedLoopLearningEngine._safe_float(payload[field], field)

        normalized["volatility"] = ClosedLoopLearningEngine._safe_float(payload.get("volatility", 0.0), "volatility")
        normalized["trend_strength"] = ClosedLoopLearningEngine._safe_float(payload.get("trend_strength", 0.0), "trend_strength")
        confidence = ClosedLoopLearningEngine._safe_float(payload.get("confidence", 0.0), "confidence")
        if confidence < 0.0 or confidence > 1.0:
            raise ClosedLoopLearningEngineError("confidence must be between 0 and 1")
        normalized["confidence"] = confidence

        if not normalized["trade_id"] or not normalized["symbol"] or not normalized["asset_class"]:
            raise ClosedLoopLearningEngineError("trade_id/symbol/asset_class must be non-empty")

        return normalized

    @staticmethod
    def _strategy_memory_record(trade: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "record_id": str(trade["trade_id"]),
            "timestamp": str(trade["timestamp_close"]),
            "strategy_id": str(trade["strategy_id"]),
            "symbol": str(trade["symbol"]),
            "asset_class": str(trade["asset_class"]),
            "market_regime": str(trade.get("market_regime") or "UNKNOWN"),
            "session": str(trade["session"]),
            "broker": str(trade["broker"]),
            "trade_id": str(trade["trade_id"]),
            "realized_pnl": float(trade["realized_pnl"]),
            "win": float(trade["realized_pnl"]) > 0.0,
            "confidence": float(trade.get("confidence", 0.0)),
        }

    @staticmethod
    def _safe_float(value: Any, field_name: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ClosedLoopLearningEngineError(f"{field_name} must be numeric") from exc
