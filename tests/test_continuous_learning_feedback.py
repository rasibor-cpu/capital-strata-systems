from __future__ import annotations

from backend.analytics.continuous_learning_feedback import ContinuousLearningFeedback
from backend.analytics.learning_pipeline_integration import LearningPipelineIntegration
from backend.analytics.regime_history_repository import RegimeHistoryRepository
from backend.analytics.strategy_memory_repository import StrategyMemoryRepository
from backend.analytics.trade_context_recorder import TradeContextRecorder
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository


def _integration(tmp_path) -> LearningPipelineIntegration:
    outcomes = TradeOutcomeRepository(tmp_path / "outcomes.json")
    regimes = RegimeHistoryRepository(tmp_path / "regimes.json")
    strategy_memory = StrategyMemoryRepository(tmp_path / "strategy_memory.json")
    outcomes.create_storage()
    regimes.create_storage()
    strategy_memory.create_storage()

    return LearningPipelineIntegration(
        trade_outcome_repository=outcomes,
        trade_context_recorder=TradeContextRecorder(),
        regime_history_repository=regimes,
        strategy_memory_repository=strategy_memory,
    )


def _trade(trade_id: str = "t-1") -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "timestamp_open": "2026-06-24T10:00:00+00:00",
        "timestamp_close": "2026-06-24T10:05:00+00:00",
        "symbol": "EUR/USD",
        "asset_class": "FX",
        "entry_price": 1.10,
        "exit_price": 1.12,
        "quantity": 10000.0,
        "realized_pnl": 25.0,
        "holding_duration_seconds": 300.0,
        "strategy_id": "alpha",
        "market_regime": "TRENDING",
        "broker": "sim",
        "session": "london-open",
        "volatility": 0.02,
        "trend_strength": 0.7,
        "confidence": 0.8,
    }


def test_continuous_learning_feedback_updates_all_surfaces(tmp_path) -> None:
    integration = _integration(tmp_path)
    feedback = ContinuousLearningFeedback(learning_pipeline=integration)

    result = feedback.process_completed_trade(
        _trade(),
        canonical_decision={"market_regime": "TRENDING", "selected_strategy": "alpha", "confidence": 0.9},
    )

    assert result["learning_result"]["trade_outcome"]["trade_id"] == "t-1"
    assert result["performance_metrics"]["trade_count"] == 1
    assert "strategy" in result["attribution"]
    assert "acceptance_threshold" in result["calibration"]
    assert isinstance(result["strategy_rankings"], list)
    assert isinstance(result["strategy_league_table"], list)
