from __future__ import annotations

from pathlib import Path

import pytest

from backend.analytics.trade_explanation_repository import TradeExplanationRepository, TradeExplanationRepositoryError


def test_trade_explanation_persistence_and_query(tmp_path: Path) -> None:
    repository = TradeExplanationRepository(tmp_path / "explanations.json")
    repository.persist_explanation({"trade_id": "t1", "strategy_id": "alpha", "market_regime": "TRENDING", "entry_reason": "trend", "exit_reason": "take_profit", "trade_quality": "A", "confidence": 0.8, "position_size": 1000.0, "capital_allocation": 2000.0, "holding_time_seconds": 1800.0, "pnl": 12.5, "decision_optimal": True})
    repository.persist_explanation({"trade_id": "t2", "strategy_id": "alpha", "market_regime": "RANGING", "entry_reason": "range", "exit_reason": "stop_loss", "trade_quality": "D", "confidence": 0.4, "position_size": 500.0, "capital_allocation": 1000.0, "holding_time_seconds": 900.0, "pnl": -2.5, "decision_optimal": False})

    assert len(repository.query_by_trade_id("t1")) == 1
    assert len(repository.query_by_strategy("alpha")) == 2
    assert len(repository.query_by_regime("TRENDING")) == 1


def test_corrupt_storage_fail_closed(tmp_path: Path) -> None:
    storage = tmp_path / "explanations.json"
    storage.write_text("not-json", encoding="utf-8")
    repository = TradeExplanationRepository(storage)

    with pytest.raises(TradeExplanationRepositoryError):
        repository.load_explanations()
