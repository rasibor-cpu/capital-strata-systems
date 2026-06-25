from __future__ import annotations

import pytest

from backend.analytics.learning_pipeline_integration import (
    LearningPipelineIntegration,
    LearningPipelineIntegrationError,
)
from backend.analytics.regime_history_repository import RegimeHistoryRepository
from backend.analytics.strategy_memory_repository import StrategyMemoryRepository
from backend.analytics.trade_context_recorder import TradeContextRecorder
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository


def _completed_trade(trade_id: str = "t-1", regime: str | None = "TRENDING", pnl: float = 12.0) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "timestamp_open": "2026-06-24T10:00:00+00:00",
        "timestamp_close": "2026-06-24T10:05:00+00:00",
        "symbol": "eur/usd",
        "asset_class": "fx",
        "entry_price": 1.10,
        "exit_price": 1.11,
        "quantity": 10000.0,
        "realized_pnl": pnl,
        "holding_duration_seconds": 300.0,
        "strategy_id": "mean_reversion",
        "market_regime": regime,
        "broker": "sim",
        "session": "london-open",
        "volatility": 0.014,
        "trend_strength": 0.61,
        "confidence": 0.83,
    }


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


def test_completed_trade_writes_all_learning_targets(tmp_path) -> None:
    integration = _integration(tmp_path)

    result = integration.write_completed_trade(_completed_trade())

    assert result["trade_outcome"]["trade_id"] == "t-1"
    assert result["trade_context"]["trade_id"] == "t-1"
    assert result["regime_history"]["regime"] == "TRENDING"
    assert result["strategy_memory"]["trade_id"] == "t-1"


def test_duplicate_completed_trade_fails_closed(tmp_path) -> None:
    integration = _integration(tmp_path)

    integration.write_completed_trade(_completed_trade("dup-trade"))

    with pytest.raises(LearningPipelineIntegrationError):
        integration.write_completed_trade(_completed_trade("dup-trade"))


def test_invalid_payload_fails_closed(tmp_path) -> None:
    integration = _integration(tmp_path)

    invalid = _completed_trade()
    invalid.pop("trade_id")

    with pytest.raises(LearningPipelineIntegrationError):
        integration.write_completed_trade(invalid)


def test_missing_regime_records_unknown(tmp_path) -> None:
    integration = _integration(tmp_path)

    result = integration.write_completed_trade(_completed_trade("t-unknown", regime=None))

    assert result["regime_history"]["regime"] == "UNKNOWN"
    assert result["trade_outcome"]["market_regime"] == "UNKNOWN"


def test_strategy_memory_receives_pnl_and_win_flag(tmp_path) -> None:
    integration = _integration(tmp_path)

    gain = integration.write_completed_trade(_completed_trade("t-win", pnl=5.0))
    loss = integration.write_completed_trade(_completed_trade("t-loss", pnl=-3.0))

    assert gain["strategy_memory"]["realized_pnl"] == 5.0
    assert gain["strategy_memory"]["win"] is True
    assert loss["strategy_memory"]["realized_pnl"] == -3.0
    assert loss["strategy_memory"]["win"] is False
