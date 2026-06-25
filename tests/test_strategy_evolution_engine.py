from __future__ import annotations

import math

from backend.analytics.autonomous_portfolio_manager import AutonomousPortfolioManager
from backend.analytics.strategy_evolution_engine import StrategyEvolutionEngine
from backend.analytics.trade_outcome_repository import TradeOutcomeRepository


def _trade(
    trade_id: str,
    strategy_id: str,
    asset_class: str,
    regime: str,
    pnl: float,
    duration: float,
) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "timestamp_open": "2026-06-01T10:00:00Z",
        "timestamp_close": "2026-06-01T10:05:00Z",
        "symbol": "EUR_USD" if asset_class == "FX" else "BTC-USD",
        "asset_class": asset_class,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "quantity": 1.0,
        "realized_pnl": pnl,
        "holding_duration_seconds": duration,
        "strategy_id": strategy_id,
        "market_regime": regime,
        "broker": "paper",
    }


def _build_learning_history() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    # alpha: improving in last 20 trades
    for i in range(80):
        pnl = 0.15 if i % 3 else -0.05
        rows.append(_trade(f"a-{i}", "alpha", "FX", "BULL", pnl, 300.0 + i))
    for i in range(20):
        pnl = 0.55 if i % 5 else -0.05
        rows.append(_trade(f"a-recent-{i}", "alpha", "FX", "BULL", pnl, 240.0 + i))

    # beta: declining and should retire
    for i in range(80):
        pnl = 0.08 if i % 4 else -0.05
        rows.append(_trade(f"b-{i}", "beta", "CRYPTO", "SIDEWAYS", pnl, 280.0 + i))
    for i in range(20):
        pnl = -0.75 if i % 2 else -0.45
        rows.append(_trade(f"b-recent-{i}", "beta", "CRYPTO", "BEAR", pnl, 330.0 + i))

    # gamma: stable
    for i in range(100):
        pnl = 0.10 if i % 2 else -0.08
        regime = "LOW_VOLATILITY" if i % 3 else "UNKNOWN"
        rows.append(_trade(f"g-{i}", "gamma", "FX", regime, pnl, 260.0 + i))

    return rows


def test_strategy_evolution_rolling_windows_and_trend(tmp_path) -> None:
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()

    engine = StrategyEvolutionEngine(repository)
    result = engine.evolve(completed_trades=_build_learning_history())

    assert result["status"] == "OK"
    alpha = next(row for row in result["strategy_registry"] if row["strategy_name"] == "alpha")
    windows = alpha["rolling_windows"]
    assert windows["20"]["status"] == "OK"
    assert windows["50"]["status"] == "OK"
    assert windows["100"]["status"] == "OK"
    assert windows["lifetime"]["trades"] == 100
    assert alpha["performance_trend"] in {"IMPROVING", "STABLE", "DECLINING"}


def test_strategy_evolution_ranking_and_weights(tmp_path) -> None:
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()

    engine = StrategyEvolutionEngine(repository)
    result = engine.evolve(completed_trades=_build_learning_history())

    rankings = result["rankings"]
    assert rankings
    top = rankings[0]
    assert "overall_score" in top
    assert "current_score" in top
    assert "confidence" in top
    assert "recommended_weight" in top
    assert "expected_contribution" in top

    total_weight = sum(float(row["recommended_weight"]) for row in rankings)
    assert math.isclose(total_weight, 1.0, rel_tol=1e-6, abs_tol=1e-6)


def test_strategy_evolution_promotion_and_retirement(tmp_path) -> None:
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()

    engine = StrategyEvolutionEngine(repository)
    result = engine.evolve(completed_trades=_build_learning_history())

    actions = {row["strategy_name"]: row["action"] for row in result["promotions"]}
    assert actions["alpha"] in {"INCREASE_ALLOCATION", "MAINTAIN_ALLOCATION"}
    assert actions["beta"] in {"REDUCE_ALLOCATION", "RETIRE_STRATEGY"}

    retirements = result["retirements"]
    assert all(row["action"] == "RETIRE_STRATEGY" for row in retirements)


def test_strategy_evolution_explainability_shape(tmp_path) -> None:
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()

    engine = StrategyEvolutionEngine(repository)
    result = engine.evolve(completed_trades=_build_learning_history())

    explain = result["explainability"]
    assert explain
    first = explain[0]
    assert "performance_trend" in first
    assert "reason" in first
    assert "confidence" in first
    assert "supporting_statistics" in first


def test_strategy_evolution_fail_closed_insufficient_data(tmp_path) -> None:
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()

    small = [_trade(f"t-{i}", "alpha", "FX", "BULL", 0.1, 120.0) for i in range(5)]
    engine = StrategyEvolutionEngine(repository)
    result = engine.evolve(completed_trades=small)

    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["rankings"] == []
    assert result["promotions"] == []
    assert result["recommended_strategy_weights"] == {}


def test_strategy_evolution_continuous_learning_updates_confidence(tmp_path) -> None:
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()

    base_rows = _build_learning_history()
    engine = StrategyEvolutionEngine(repository)

    before = engine.evolve(completed_trades=base_rows)
    after = engine.evolve(
        completed_trades=base_rows
        + [_trade("alpha-new", "alpha", "FX", "BULL", 0.95, 150.0)]
    )

    before_alpha = next(row for row in before["strategy_registry"] if row["strategy_name"] == "alpha")
    after_alpha = next(row for row in after["strategy_registry"] if row["strategy_name"] == "alpha")
    assert after_alpha["trades"] == before_alpha["trades"] + 1
    assert after_alpha["current_confidence"] >= before_alpha["current_confidence"]


def test_portfolio_manager_consumes_strategy_weights_from_evolution(tmp_path) -> None:
    repository = TradeOutcomeRepository(tmp_path / "outcomes.json")
    repository.create_storage()

    evolution = StrategyEvolutionEngine(repository).evolve(completed_trades=_build_learning_history())
    weights = evolution["recommended_strategy_weights"]

    manager = AutonomousPortfolioManager()
    result = manager.recommend(
        opportunities=[
            {
                "symbol": "EUR_USD",
                "asset_class": "FX",
                "selected_strategy": "alpha",
                "market_regime": "BULL",
                "confidence": 0.75,
                "opportunity_score": 75.0,
                "expected_reward": 35.0,
                "expected_risk": 14.0,
            },
            {
                "symbol": "BTC-USD",
                "asset_class": "CRYPTO",
                "selected_strategy": "beta",
                "market_regime": "BEAR",
                "confidence": 0.55,
                "opportunity_score": 58.0,
                "expected_reward": 40.0,
                "expected_risk": 30.0,
            },
        ],
        current_positions=[],
        total_capital=100000.0,
        available_capital=80000.0,
        reserved_capital=20000.0,
        learning_records=_build_learning_history(),
        strategy_weight_recommendations=weights,
    )

    per_strategy = result["portfolio_allocation"]["per_strategy"]
    assert per_strategy
    assert "recommended_strategy_weights" in result["portfolio_allocation"]
    assert set(per_strategy.keys()).issubset(set(weights.keys()))
