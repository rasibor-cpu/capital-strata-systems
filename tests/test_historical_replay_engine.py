from __future__ import annotations

import pytest

from backend.intelligence.intelligence_orchestrator import IntelligenceDecision, IntelligenceOrchestrator
from backend.validation.historical_replay_engine import HistoricalReplayEngine, HistoricalReplayEngineError


class FakeMarketRegimeEngine:
    def analyze_market(self, candles):
        return {
            "market_regime": "TRENDING",
            "confidence": 0.9,
            "volatility": 0.02,
            "trend_strength": 0.7,
        }


class FakeStrategyIntelligenceEngine:
    def __init__(self, selected_by_symbol: dict[str, str]) -> None:
        self.selected_by_symbol = selected_by_symbol

    def rank_strategies_by_context(self, *, symbol=None, asset_class=None, market_regime=None, session=None):
        selected = self.selected_by_symbol.get(str(symbol).upper(), "alpha")
        return [
            {
                "strategy_id": selected,
                "trade_count": 3,
                "realized_pnl": 10.0,
                "average_pnl": 3.3,
                "win_rate": 0.7,
                "confidence": 0.8,
                "ranking_score": 0.84,
            }
        ]

    def best_strategy_for_symbol(self, symbol):
        strategy_id = self.selected_by_symbol.get(str(symbol).upper(), "alpha")
        return {"strategy_id": strategy_id, "ranking_score": 0.84}

    def best_strategy_for_regime(self, market_regime):
        return {"strategy_id": "alpha", "ranking_score": 0.84}

    def strategy_confidence(self, strategy_id, **kwargs):
        return 0.84 if strategy_id in {"alpha", "beta"} else 0.4

    def strategy_memory_summary(self):
        return {"record_count": 2}


class FakeCapitalAllocationEngine:
    def allocate(self, ranking, **kwargs):
        row = ranking[0]
        return [
            {
                "symbol": row["symbol"],
                "score": float(row["score"]),
                "trade_count": int(row["trade_count"]),
                "realized_pnl": float(row["realized_pnl"]),
                "allocation_weight": 0.3,
                "allocation_amount": 3000.0,
                "status": "PREFERRED",
            }
        ]


class FakeAdaptivePositionSizingEngine:
    def size_positions(self, allocations, **kwargs):
        row = allocations[0]
        return [
            {
                "symbol": row["symbol"],
                "recommended_position_size": 250.0,
                "recommended_capital": 250.0,
                "confidence": kwargs["confidence"],
                "sizing_reason": "confidence_and_risk_adjusted",
                "sizing_status": "APPROVED",
            }
        ]


class FakePortfolioCorrelationEngine:
    def analyze_portfolio(self, positions):
        return {
            "total_exposure": 2000.0,
            "by_asset_class": {"EQUITY": 2000.0},
            "by_symbol": {"AAPL": 1000.0, "MSFT": 1000.0},
            "long_exposure": 1200.0,
            "short_exposure": 800.0,
            "directional_exposure": 400.0,
            "directional_concentration": 0.2,
            "concentration_score": 0.2,
            "correlation_score": 0.2,
            "grouped_exposure": {},
            "correlation_groups": {},
        }


class FakeConcentrationGuard:
    def evaluate(self, positions):
        return {
            "risk_score": 0.2,
            "concentration_score": 0.2,
            "correlation_score": 0.2,
            "recommendation": "ALLOW",
            "portfolio_summary": {"total_exposure": 2000.0},
        }


class FakeAdaptiveExitEngine:
    def recommend_exit(self, **kwargs):
        return {
            "trade_id": kwargs["open_trade_context"]["trade_id"],
            "symbol": kwargs["open_trade_context"]["symbol"],
            "action": "HOLD",
            "exit_reason": "TEST",
            "confidence": 0.85,
            "recommended_stop": 99.0,
            "recommended_take_profit": 102.0,
            "recommended_trailing_stop": 98.0,
            "max_hold_seconds": 3600,
        }


def _make_history() -> list[dict[str, object]]:
    return [
        {
            "timestamp": "2026-06-24T10:00:00+00:00",
            "trade_id": "trade-1",
            "symbol": "AAPL",
            "asset_class": "EQUITY",
            "direction": "LONG",
            "strategy": "mean",
            "current_price": 100.0,
            "market_snapshot": {
                "candles": [
                    {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0, "volume": 1000.0},
                    {"open": 100.0, "high": 102.0, "low": 99.5, "close": 101.0, "volume": 1015.0},
                    {"open": 101.0, "high": 103.0, "low": 100.5, "close": 102.0, "volume": 1030.0},
                ]
            },
            "portfolio_snapshot": {
                "available_capital": 10000.0,
                "positions": [
                    {"symbol": "AAPL", "asset_class": "EQUITY", "exposure_value": 1000.0, "side": "LONG"},
                    {"symbol": "MSFT", "asset_class": "EQUITY", "exposure_value": 1000.0, "side": "SHORT"},
                ],
            },
        },
        {
            "timestamp": "2026-06-24T10:05:00+00:00",
            "trade_id": "trade-2",
            "symbol": "MSFT",
            "asset_class": "EQUITY",
            "direction": "LONG",
            "strategy": "breakout",
            "current_price": 200.0,
            "market_snapshot": {
                "candles": [
                    {"open": 198.0, "high": 201.0, "low": 197.5, "close": 199.0, "volume": 1200.0},
                    {"open": 199.0, "high": 203.0, "low": 198.5, "close": 202.0, "volume": 1220.0},
                    {"open": 202.0, "high": 205.0, "low": 201.0, "close": 204.0, "volume": 1250.0},
                ]
            },
            "portfolio_snapshot": {
                "available_capital": 10000.0,
                "positions": [
                    {"symbol": "AAPL", "asset_class": "EQUITY", "exposure_value": 1000.0, "side": "LONG"},
                    {"symbol": "MSFT", "asset_class": "EQUITY", "exposure_value": 1000.0, "side": "SHORT"},
                ],
            },
        },
    ]


def _build_engine() -> HistoricalReplayEngine:
    orchestrator = IntelligenceOrchestrator(
        market_regime_engine=FakeMarketRegimeEngine(),
        strategy_intelligence_engine=FakeStrategyIntelligenceEngine({"AAPL": "alpha", "MSFT": "beta"}),
        capital_allocation_engine=FakeCapitalAllocationEngine(),
        adaptive_position_sizing_engine=FakeAdaptivePositionSizingEngine(),
        portfolio_correlation_engine=FakePortfolioCorrelationEngine(),
        concentration_guard=FakeConcentrationGuard(),
        adaptive_exit_engine=FakeAdaptiveExitEngine(),
    )

    return HistoricalReplayEngine(
        orchestrator=orchestrator,
        market_regime_engine=orchestrator.market_regime_engine,
        strategy_intelligence_engine=orchestrator.strategy_intelligence_engine,
        capital_allocation_engine=orchestrator.capital_allocation_engine,
        adaptive_position_sizing_engine=orchestrator.adaptive_position_sizing_engine,
        portfolio_correlation_engine=orchestrator.portfolio_correlation_engine,
        concentration_guard=orchestrator.concentration_guard,
        adaptive_exit_engine=orchestrator.adaptive_exit_engine,
    )


def test_single_replay() -> None:
    engine = _build_engine()
    decisions = engine.replay([_make_history()[0]])

    assert len(decisions) == 1
    assert decisions[0].symbol == "AAPL"
    assert decisions[0].market_regime == "TRENDING"
    assert decisions[0].selected_strategy == "alpha"
    assert decisions[0].decision == "ALLOW"


def test_multiple_replay() -> None:
    engine = _build_engine()
    decisions = engine.replay(_make_history())

    assert len(decisions) == 2
    assert [decision.selected_strategy for decision in decisions] == ["alpha", "beta"]
    assert [decision.symbol for decision in decisions] == ["AAPL", "MSFT"]


def test_deterministic_replay() -> None:
    engine = _build_engine()
    history = _make_history()

    assert engine.replay(history) == engine.replay(history)


def test_empty_history() -> None:
    engine = _build_engine()

    assert engine.replay([]) == []
    run_result = engine.replay_with_statistics([])
    assert run_result.decisions == []
    assert run_result.statistics["number_of_candidates"] == 0


def test_corrupt_history() -> None:
    engine = _build_engine()

    with pytest.raises(HistoricalReplayEngineError):
        engine.replay([
            {
                "timestamp": "2026-06-24T10:00:00+00:00",
                "trade_id": "broken",
                "symbol": "BTC-USD",
                "asset_class": "MAGIC",
                "direction": "LONG",
                "strategy": "alpha",
                "current_price": 100.0,
                "market_snapshot": {"candles": []},
                "portfolio_snapshot": {"positions": []},
            }
        ])


def test_fail_closed_behavior() -> None:
    engine = _build_engine()

    with pytest.raises(HistoricalReplayEngineError):
        engine.replay(
            [
                {
                    "timestamp": "2026-06-24T10:00:00+00:00",
                    "trade_id": "broken",
                    "symbol": "AAPL",
                    "asset_class": "EQUITY",
                    "direction": "LONG",
                    "strategy": "alpha",
                    "market_snapshot": {"candles": []},
                    "portfolio_snapshot": {"positions": []},
                }
            ]
        )
