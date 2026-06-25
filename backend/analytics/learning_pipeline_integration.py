from __future__ import annotations

from typing import Any, Mapping

from backend.analytics.regime_history_repository import (
    RegimeHistoryRepository,
    RegimeHistoryRepositoryError,
)
from backend.analytics.strategy_memory_repository import (
    DuplicateStrategyMemoryError,
    StrategyMemoryRepository,
    StrategyMemoryRepositoryError,
)
from backend.analytics.trade_context_recorder import (
    TradeContextRecorder,
    TradeContextRecorderError,
)
from backend.analytics.trade_outcome_repository import (
    DuplicateTradeOutcomeError,
    TradeOutcomeRepository,
    TradeOutcomeRepositoryError,
)


class LearningPipelineIntegrationError(RuntimeError):
    """Fail-closed exception for completed trade learning writes."""


class LearningPipelineIntegration:
    """Writes canonical completed trade data into all learning repositories."""

    _SUPPORTED_REGIMES = {
        "TRENDING",
        "RANGING",
        "BREAKOUT",
        "REVERSAL",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "UNKNOWN",
    }

    def __init__(
        self,
        *,
        trade_outcome_repository: TradeOutcomeRepository,
        trade_context_recorder: TradeContextRecorder,
        regime_history_repository: RegimeHistoryRepository,
        strategy_memory_repository: StrategyMemoryRepository,
    ) -> None:
        self.trade_outcome_repository = trade_outcome_repository
        self.trade_context_recorder = trade_context_recorder
        self.regime_history_repository = regime_history_repository
        self.strategy_memory_repository = strategy_memory_repository

    def write_completed_trade(self, completed_trade: Mapping[str, Any]) -> dict[str, Any]:
        payload = self._validate_completed_trade(completed_trade)

        regime = str(payload.get("market_regime") or "").strip().upper() or "UNKNOWN"
        if regime not in self._SUPPORTED_REGIMES:
            regime = "UNKNOWN"

        try:
            outcome = self.trade_outcome_repository.append_outcome(
                {
                    "trade_id": payload["trade_id"],
                    "timestamp_open": payload["timestamp_open"],
                    "timestamp_close": payload["timestamp_close"],
                    "symbol": payload["symbol"],
                    "asset_class": payload["asset_class"],
                    "entry_price": payload["entry_price"],
                    "exit_price": payload["exit_price"],
                    "quantity": payload["quantity"],
                    "realized_pnl": payload["realized_pnl"],
                    "holding_duration_seconds": payload["holding_duration_seconds"],
                    "strategy_id": payload["strategy_id"],
                    "market_regime": regime,
                    "broker": payload["broker"],
                }
            )
        except (DuplicateTradeOutcomeError, TradeOutcomeRepositoryError) as exc:
            raise LearningPipelineIntegrationError(f"Trade outcome write failed: {exc}") from exc

        try:
            context = self.trade_context_recorder.record_context(
                {
                    "trade_id": payload["trade_id"],
                    "symbol": payload["symbol"],
                    "asset_class": payload["asset_class"],
                    "strategy": payload["strategy_id"],
                    "entry_time": payload["timestamp_open"],
                    "exit_time": payload["timestamp_close"],
                    "market_regime": regime,
                    "volatility": payload["volatility"],
                    "trend_strength": payload["trend_strength"],
                    "confidence": payload["confidence"],
                    "broker": payload["broker"],
                    "session": payload["session"],
                }
            )
        except TradeContextRecorderError as exc:
            raise LearningPipelineIntegrationError(f"Trade context write failed: {exc}") from exc

        try:
            regime_history = self.regime_history_repository.append_regime(
                {
                    "timestamp": payload["timestamp_close"],
                    "regime": regime,
                    "symbol": payload["symbol"],
                    "confidence": payload["confidence"],
                }
            )
        except RegimeHistoryRepositoryError as exc:
            raise LearningPipelineIntegrationError(f"Regime history write failed: {exc}") from exc

        win = float(payload["realized_pnl"]) > 0
        try:
            strategy_memory = self.strategy_memory_repository.persist_memory_record(
                {
                    "record_id": payload["trade_id"],
                    "timestamp": payload["timestamp_close"],
                    "strategy_id": payload["strategy_id"],
                    "symbol": payload["symbol"],
                    "asset_class": payload["asset_class"],
                    "market_regime": regime,
                    "session": payload["session"],
                    "broker": payload["broker"],
                    "trade_id": payload["trade_id"],
                    "realized_pnl": payload["realized_pnl"],
                    "win": win,
                    "confidence": payload["confidence"],
                }
            )
        except (DuplicateStrategyMemoryError, StrategyMemoryRepositoryError) as exc:
            raise LearningPipelineIntegrationError(f"Strategy memory write failed: {exc}") from exc

        return {
            "trade_outcome": outcome,
            "trade_context": context,
            "regime_history": regime_history,
            "strategy_memory": strategy_memory,
        }

    @staticmethod
    def _validate_completed_trade(payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise LearningPipelineIntegrationError("Completed trade payload must be a mapping")

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
            raise LearningPipelineIntegrationError(
                f"Completed trade missing required fields: {', '.join(missing)}"
            )

        normalized: dict[str, Any] = {}
        for field in {
            "trade_id",
            "timestamp_open",
            "timestamp_close",
            "symbol",
            "asset_class",
            "strategy_id",
            "broker",
            "session",
        }:
            value = str(payload[field]).strip()
            if not value:
                raise LearningPipelineIntegrationError(
                    f"Completed trade field {field} must be non-empty"
                )
            if field in {"symbol", "asset_class"}:
                value = value.upper()
            normalized[field] = value

        for field in {
            "entry_price",
            "exit_price",
            "quantity",
            "realized_pnl",
            "holding_duration_seconds",
        }:
            try:
                normalized[field] = float(payload[field])
            except (TypeError, ValueError) as exc:
                raise LearningPipelineIntegrationError(
                    f"Completed trade field {field} must be numeric"
                ) from exc

        # Learning features are required for context and regime history.
        try:
            normalized["volatility"] = float(payload.get("volatility", 0.0))
            normalized["trend_strength"] = float(payload.get("trend_strength", 0.0))
            normalized["confidence"] = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError) as exc:
            raise LearningPipelineIntegrationError(
                "Completed trade features volatility/trend_strength/confidence must be numeric"
            ) from exc

        if normalized["confidence"] < 0 or normalized["confidence"] > 1:
            raise LearningPipelineIntegrationError("Completed trade confidence must be between 0 and 1")

        normalized["market_regime"] = str(payload.get("market_regime") or "").strip()

        return normalized
