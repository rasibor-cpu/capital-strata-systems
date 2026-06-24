import pytest

from backend.analytics.profitability_ranking_engine import (
    ProfitabilityRankingEngine,
    ProfitabilityRankingEngineError,
)
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository


def outcome(trade_id, symbol, asset_class, strategy_id, pnl):
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


@pytest.fixture
def populated_repo(repo):
    rows = [
        outcome("t1", "AAPL", "equity", "mean", 10.0),
        outcome("t2", "AAPL", "equity", "mean", 5.0),
        outcome("t3", "AAPL", "equity", "breakout", -1.0),
        outcome("t4", "MSFT", "equity", "breakout", -8.0),
        outcome("t5", "MSFT", "equity", "breakout", -2.0),
        outcome("t6", "EURUSD", "fx", "mean", 4.0),
    ]
    for row in rows:
        repo.append_outcome(row)
    return repo


def test_symbol_ranking(populated_repo):
    ranked = ProfitabilityRankingEngine(populated_repo, minimum_trade_count=2).rank_symbols()

    assert [row["symbol"] for row in ranked] == ["AAPL", "EURUSD", "MSFT"]
    assert ranked[0] == {
        "symbol": "AAPL",
        "trade_count": 3,
        "realized_pnl": 14.0,
        "win_count": 2,
        "loss_count": 1,
        "win_rate": pytest.approx(2 / 3),
        "average_pnl": pytest.approx(14 / 3),
        "score": pytest.approx((14.0 * 0.60) + ((2 / 3) * 100.0 * 0.25) + ((14 / 3) * 0.15)),
    }


def test_asset_class_ranking(populated_repo):
    ranked = ProfitabilityRankingEngine(populated_repo, minimum_trade_count=2).rank_asset_classes()

    assert [row["asset_class"] for row in ranked] == ["fx", "equity"]
    assert ranked[0]["trade_count"] == 1
    assert ranked[0]["realized_pnl"] == 4.0
    assert ranked[0]["win_count"] == 1
    assert ranked[0]["loss_count"] == 0


def test_strategy_ranking(populated_repo):
    ranked = ProfitabilityRankingEngine(populated_repo, minimum_trade_count=2).rank_strategies()

    assert [row["strategy_id"] for row in ranked] == ["mean", "breakout"]
    assert ranked[0]["trade_count"] == 3
    assert ranked[0]["realized_pnl"] == 19.0
    assert ranked[0]["win_rate"] == 1.0


def test_preferred_symbols(populated_repo):
    preferred = ProfitabilityRankingEngine(populated_repo, minimum_trade_count=2).preferred_symbols()

    assert [row["symbol"] for row in preferred] == ["AAPL"]


def test_restricted_symbols(populated_repo):
    restricted = ProfitabilityRankingEngine(populated_repo, minimum_trade_count=2).restricted_symbols()

    assert [row["symbol"] for row in restricted] == ["MSFT", "EURUSD"]
    assert restricted[0]["score"] < restricted[1]["score"]


def test_minimum_trade_count_behavior(populated_repo):
    ranked = ProfitabilityRankingEngine(populated_repo, minimum_trade_count=3).rank_symbols()
    eurusd = next(row for row in ranked if row["symbol"] == "EURUSD")

    assert eurusd["trade_count"] == 1
    assert eurusd["score"] == pytest.approx(((4.0 * 0.60) + (1.0 * 100.0 * 0.25) + (4.0 * 0.15)) / 3)
    assert [row["symbol"] for row in ProfitabilityRankingEngine(populated_repo, minimum_trade_count=3).preferred_symbols()] == ["AAPL"]
    assert "EURUSD" in [row["symbol"] for row in ProfitabilityRankingEngine(populated_repo, minimum_trade_count=3).restricted_symbols()]


def test_fail_closed_invalid_limit(populated_repo):
    engine = ProfitabilityRankingEngine(populated_repo)

    with pytest.raises(ProfitabilityRankingEngineError):
        engine.rank_symbols(limit=0)
    with pytest.raises(ProfitabilityRankingEngineError):
        engine.preferred_symbols(limit=-1)
    with pytest.raises(ProfitabilityRankingEngineError):
        ProfitabilityRankingEngine(populated_repo, minimum_trade_count=0)


def test_empty_warehouse_behavior(repo):
    engine = ProfitabilityRankingEngine(repo)

    assert engine.rank_symbols() == []
    assert engine.rank_asset_classes() == []
    assert engine.rank_strategies() == []
    assert engine.preferred_symbols() == []
    assert engine.restricted_symbols() == []
