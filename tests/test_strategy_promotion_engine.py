import pytest

from backend.analytics import StrategyPromotionEngine, StrategyPromotionError
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository


def outcome(trade_id, strategy_id, pnl):
    return {
        "trade_id": trade_id,
        "timestamp_open": "2026-06-24T10:00:00+00:00",
        "timestamp_close": "2026-06-24T10:05:00+00:00",
        "symbol": "AAPL",
        "asset_class": "equity",
        "entry_price": 100.0,
        "exit_price": 110.0,
        "quantity": 1.0,
        "realized_pnl": pnl,
        "holding_duration_seconds": 300.0,
        "strategy_id": strategy_id,
        "market_regime": "risk_on",
        "broker": "sim",
    }


def test_promotion_and_demotion(tmp_path):
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()
    for row in [
        outcome("t1", "mean", 50.0),
        outcome("t2", "mean", 40.0),
        outcome("t3", "mean", 30.0),
        outcome("t4", "breakout", -20.0),
        outcome("t5", "breakout", -10.0),
    ]:
        repository.append_outcome(row)

    from backend.analytics.profitability_ranking_engine import ProfitabilityRankingEngine
    from backend.analytics.adaptive_position_sizing import AdaptivePositionSizingEngine

    ranking_engine = ProfitabilityRankingEngine(repository, minimum_trade_count=2)
    sizing_engine = AdaptivePositionSizingEngine()
    promotion_engine = StrategyPromotionEngine(repository, ranking_engine, sizing_engine)

    recommendations = promotion_engine.recommend()
    mean = next(item for item in recommendations if item["strategy_id"] == "mean")
    breakout = next(item for item in recommendations if item["strategy_id"] == "breakout")

    assert mean["recommendation"] == "PROMOTE"
    assert breakout["recommendation"] == "DEMOTE"


def test_fail_closed_on_invalid_repository(tmp_path):
    repository = TradeOutcomeRepository(tmp_path / "missing.json")

    from backend.analytics.profitability_ranking_engine import ProfitabilityRankingEngine
    from backend.analytics.adaptive_position_sizing import AdaptivePositionSizingEngine

    with pytest.raises(StrategyPromotionError):
        StrategyPromotionEngine(repository, ProfitabilityRankingEngine(repository), AdaptivePositionSizingEngine()).recommend()
