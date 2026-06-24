import json

import pytest

from backend.analytics.trade_outcome_repository import (
    DuplicateTradeOutcomeError,
    TradeOutcomeRepository,
    TradeOutcomeRepositoryError,
    build_trade_outcome_analytics_adapter,
    persist_completed_trade_outcome,
)


def outcome(trade_id="t1", symbol="AAPL", asset_class="equity", strategy_id="mean", pnl=10.0):
    return {
        "trade_id": trade_id,
        "timestamp_open": "2026-06-24T10:00:00+00:00",
        "timestamp_close": "2026-06-24T10:05:00+00:00",
        "symbol": symbol,
        "asset_class": asset_class,
        "entry_price": 100.0,
        "exit_price": 110.0,
        "quantity": 1.0,
        "realized_pnl": pnl,
        "holding_duration_seconds": 300.0,
        "strategy_id": strategy_id,
        "market_regime": "risk_on",
        "broker": "sim",
    }


@pytest.fixture
def repo(tmp_path):
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()
    return repository


def test_repository_creation(repo):
    assert repo.storage_path.exists()
    assert repo.load_outcomes() == []


def test_persistence_and_reload(repo):
    saved = repo.append_outcome(outcome())
    reloaded = TradeOutcomeRepository(repo.storage_path).load_outcomes()
    assert saved == reloaded[0]
    assert reloaded[0]["trade_id"] == "t1"


def test_duplicate_prevention(repo):
    repo.append_outcome(outcome())
    with pytest.raises(DuplicateTradeOutcomeError):
        repo.append_outcome(outcome())


def test_aggregation_by_symbol(repo):
    repo.append_outcome(outcome("t1", symbol="AAPL", pnl=10.0))
    repo.append_outcome(outcome("t2", symbol="MSFT", pnl=-2.0))
    repo.append_outcome(outcome("t3", symbol="AAPL", pnl=5.0))
    assert repo.aggregate_by_symbol() == [
        {"symbol": "AAPL", "trade_count": 2, "realized_pnl": 15.0},
        {"symbol": "MSFT", "trade_count": 1, "realized_pnl": -2.0},
    ]


def test_aggregation_by_asset_class(repo):
    repo.append_outcome(outcome("t1", asset_class="equity", pnl=7.0))
    repo.append_outcome(outcome("t2", asset_class="fx", pnl=3.0))
    repo.append_outcome(outcome("t3", asset_class="equity", pnl=-1.0))
    assert repo.aggregate_by_asset_class() == [
        {"asset_class": "equity", "trade_count": 2, "realized_pnl": 6.0},
        {"asset_class": "fx", "trade_count": 1, "realized_pnl": 3.0},
    ]


def test_aggregation_by_strategy(repo):
    repo.append_outcome(outcome("t1", strategy_id="breakout", pnl=4.0))
    repo.append_outcome(outcome("t2", strategy_id="mean", pnl=6.0))
    repo.append_outcome(outcome("t3", strategy_id="breakout", pnl=1.0))
    assert repo.aggregate_by_strategy_id() == [
        {"strategy_id": "breakout", "trade_count": 2, "realized_pnl": 5.0},
        {"strategy_id": "mean", "trade_count": 1, "realized_pnl": 6.0},
    ]


def test_fail_closed_behavior_for_missing_storage(tmp_path):
    with pytest.raises(TradeOutcomeRepositoryError):
        TradeOutcomeRepository(tmp_path / "missing.json").load_outcomes()


def test_fail_closed_behavior_for_corrupt_storage(tmp_path):
    path = tmp_path / "outcomes.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(TradeOutcomeRepositoryError):
        TradeOutcomeRepository(path).load_outcomes()


def test_fail_closed_behavior_for_invalid_record(repo):
    invalid = outcome()
    invalid.pop("trade_id")
    with pytest.raises(TradeOutcomeRepositoryError):
        repo.append_outcome(invalid)


def test_analytics_adapter_output(repo):
    persist_completed_trade_outcome(repo, outcome("t1", symbol="AAPL", asset_class="equity", strategy_id="mean", pnl=10.0))
    repo.append_outcome(outcome("t2", symbol="MSFT", asset_class="equity", strategy_id="breakout", pnl=-5.0))
    repo.append_outcome(outcome("t3", symbol="EURUSD", asset_class="fx", strategy_id="mean", pnl=2.0))

    result = build_trade_outcome_analytics_adapter(repo, limit=2)

    assert result["top_symbols"][0]["symbol"] == "AAPL"
    assert result["worst_symbols"][0]["symbol"] == "MSFT"
    assert result["top_asset_classes"][0] == {"asset_class": "equity", "trade_count": 2, "realized_pnl": 5.0}
    assert result["top_strategies"][0] == {"strategy_id": "mean", "trade_count": 2, "realized_pnl": 12.0}


def test_duplicate_trade_ids_in_storage_fail_closed(tmp_path):
    path = tmp_path / "outcomes.json"
    duplicated = [outcome(), outcome()]
    path.write_text(json.dumps(duplicated), encoding="utf-8")
    with pytest.raises(DuplicateTradeOutcomeError):
        TradeOutcomeRepository(path).load_outcomes()
