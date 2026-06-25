from __future__ import annotations

import pytest

from backend.intelligence.intelligence_orchestrator import (
    IntelligenceDecisionError,
    IntelligenceOrchestrator,
)


class FakeMarketRegimeEngine:
    def __init__(self, response: dict[str, object] | None = None, *, raises: Exception | None = None) -> None:
        self.response = response or {
            "market_regime": "TRENDING",
            "confidence": 0.9,
            "volatility": 0.02,
            "trend_strength": 0.7,
        }
        self.raises = raises

    def analyze_market(self, candles):
        if self.raises is not None:
            raise self.raises
        return self.response


class FakeStrategyIntelligenceEngine:
    def __init__(self, score: float = 0.8, best: dict[str, object] | None = None) -> None:
        self.score = score
        self.best = best or {
            "strategy_id": "alpha",
            "ranking_score": score,
        }

    def strategy_confidence(self, strategy_id, **kwargs):
        return self.score if strategy_id == "alpha" else self.score / 2.0

    def best_strategy_for_symbol(self, symbol):
        return self.best

    def best_strategy_for_regime(self, market_regime):
        return self.best

    def strategy_memory_summary(self):
        return {"record_count": 2}


class FakeCapitalAllocationEngine:
    def __init__(self, weight: float = 0.3) -> None:
        self.weight = weight

    def allocate(self, ranking, **kwargs):
        symbol = ranking[0]["symbol"]
        return [
            {
                "symbol": symbol,
                "score": float(ranking[0]["score"]),
                "trade_count": 1,
                "realized_pnl": 0.0,
                "allocation_weight": self.weight,
                "allocation_amount": kwargs["available_capital"] * self.weight,
                "status": "PREFERRED",
            }
        ]


class FakeAdaptivePositionSizingEngine:
    def __init__(self, position_size: float = 250.0) -> None:
        self.position_size = position_size

    def size_positions(self, allocations, **kwargs):
        symbol = allocations[0]["symbol"]
        return [
            {
                "symbol": symbol,
                "recommended_position_size": self.position_size,
                "recommended_capital": self.position_size,
                "confidence": kwargs["confidence"],
                "sizing_reason": "confidence_and_risk_adjusted",
                "sizing_status": "APPROVED",
            }
        ]


class FakePortfolioCorrelationEngine:
    def __init__(self, concentration_score: float = 0.2) -> None:
        self.concentration_score = concentration_score

    def analyze_portfolio(self, positions):
        return {
            "total_exposure": 1000.0,
            "by_asset_class": {"EQUITY": 1000.0},
            "by_symbol": {"AAPL": 1000.0},
            "long_exposure": 600.0,
            "short_exposure": 400.0,
            "directional_exposure": 200.0,
            "directional_concentration": 0.2,
            "concentration_score": self.concentration_score,
            "correlation_score": 0.2,
            "grouped_exposure": {},
            "correlation_groups": {},
        }


class FakeConcentrationGuard:
    def __init__(self, recommendation: str = "ALLOW", risk_score: float = 0.2, concentration_score: float = 0.2) -> None:
        self.recommendation = recommendation
        self.risk_score = risk_score
        self.concentration_score = concentration_score

    def evaluate(self, positions):
        return {
            "risk_score": self.risk_score,
            "concentration_score": self.concentration_score,
            "correlation_score": self.concentration_score,
            "recommendation": self.recommendation,
            "portfolio_summary": {"total_exposure": 1000.0},
        }


class FakeAdaptiveExitEngine:
    def __init__(self, action: str = "HOLD", confidence: float = 0.75) -> None:
        self.action = action
        self.confidence = confidence

    def recommend_exit(self, **kwargs):
        return {
            "trade_id": kwargs["open_trade_context"]["trade_id"],
            "symbol": kwargs["open_trade_context"]["symbol"],
            "action": self.action,
            "exit_reason": "TEST",
            "confidence": self.confidence,
            "recommended_stop": 99.0,
            "recommended_take_profit": 101.0,
            "recommended_trailing_stop": 98.5,
            "max_hold_seconds": 3600,
        }


def _candidate() -> dict[str, object]:
    return {
        "trade_id": "trade-1",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "direction": "LONG",
        "strategy": "alpha",
        "current_price": 100.0,
        "market_snapshot": {
            "candles": [
                {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0, "volume": 1000.0},
                {"open": 100.0, "high": 102.0, "low": 99.5, "close": 101.0, "volume": 1010.0},
                {"open": 101.0, "high": 103.0, "low": 100.5, "close": 102.0, "volume": 1020.0},
            ]
        },
        "portfolio_snapshot": {
            "available_capital": 10000.0,
            "positions": [
                {"symbol": "MSFT", "asset_class": "EQUITY", "exposure_value": 1000.0, "side": "LONG"},
                {"symbol": "TLT", "asset_class": "BOND", "exposure_value": 1000.0, "side": "SHORT"},
            ],
        },
    }


def _build_orchestrator(*, guard: FakeConcentrationGuard | None = None, exit_engine: FakeAdaptiveExitEngine | None = None, strategy_score: float = 0.8, allocation_weight: float = 0.3, position_size: float = 250.0, market_regime: str = "TRENDING") -> IntelligenceOrchestrator:
    return IntelligenceOrchestrator(
        market_regime_engine=FakeMarketRegimeEngine({
            "market_regime": market_regime,
            "confidence": 0.9,
            "volatility": 0.02,
            "trend_strength": 0.7,
        }),
        strategy_intelligence_engine=FakeStrategyIntelligenceEngine(score=strategy_score),
        capital_allocation_engine=FakeCapitalAllocationEngine(weight=allocation_weight),
        adaptive_position_sizing_engine=FakeAdaptivePositionSizingEngine(position_size=position_size),
        portfolio_correlation_engine=FakePortfolioCorrelationEngine(concentration_score=0.2),
        concentration_guard=guard or FakeConcentrationGuard(),
        adaptive_exit_engine=exit_engine or FakeAdaptiveExitEngine(),
    )


def test_successful_orchestration() -> None:
    orchestrator = _build_orchestrator()

    result = orchestrator.decide(_candidate())

    assert result.market_regime == "TRENDING"
    assert result.decision == "ALLOW"
    assert result.overall_confidence > 0.0
    assert result.diagnostics["candidate"]["symbol"] == "AAPL"


def test_missing_engine() -> None:
    orchestrator = IntelligenceOrchestrator(
        market_regime_engine=FakeMarketRegimeEngine(),
        strategy_intelligence_engine=FakeStrategyIntelligenceEngine(),
        capital_allocation_engine=FakeCapitalAllocationEngine(),
        adaptive_position_sizing_engine=FakeAdaptivePositionSizingEngine(),
        portfolio_correlation_engine=FakePortfolioCorrelationEngine(),
        concentration_guard=None,
        adaptive_exit_engine=FakeAdaptiveExitEngine(),
    )

    with pytest.raises(IntelligenceDecisionError):
        orchestrator.decide(_candidate())


def test_invalid_candidate() -> None:
    orchestrator = _build_orchestrator()

    with pytest.raises(IntelligenceDecisionError):
        orchestrator.decide({"trade_id": "bad"})

    bad_candidate = _candidate()
    bad_candidate["current_price"] = 0
    with pytest.raises(IntelligenceDecisionError):
        orchestrator.decide(bad_candidate)


def test_blocked_recommendation() -> None:
    orchestrator = _build_orchestrator(
        guard=FakeConcentrationGuard(recommendation="BLOCK", risk_score=0.9, concentration_score=0.9),
        exit_engine=FakeAdaptiveExitEngine(action="STOP_LOSS", confidence=0.95),
    )

    result = orchestrator.decide(_candidate())

    assert result.decision == "BLOCK"
    assert result.portfolio_risk == pytest.approx(0.9)


def test_reduced_size_recommendation() -> None:
    orchestrator = _build_orchestrator(
        guard=FakeConcentrationGuard(recommendation="REDUCE_SIZE", risk_score=0.55, concentration_score=0.55),
        exit_engine=FakeAdaptiveExitEngine(action="REDUCE", confidence=0.7),
    )

    result = orchestrator.decide(_candidate())

    assert result.decision == "REDUCE_SIZE"
    assert result.concentration_score == pytest.approx(0.55)


def test_allow_recommendation() -> None:
    orchestrator = _build_orchestrator(
        guard=FakeConcentrationGuard(recommendation="ALLOW", risk_score=0.1, concentration_score=0.1),
        exit_engine=FakeAdaptiveExitEngine(action="HOLD", confidence=0.9),
    )

    result = orchestrator.decide(_candidate())

    assert result.decision == "ALLOW"
    assert result.portfolio_risk < 0.2


def test_deterministic_output() -> None:
    orchestrator = _build_orchestrator()
    candidate = _candidate()

    assert orchestrator.decide(candidate) == orchestrator.decide(candidate)


def test_fail_closed_behavior() -> None:
    orchestrator = IntelligenceOrchestrator(
        market_regime_engine=FakeMarketRegimeEngine(raises=RuntimeError("boom")),
        strategy_intelligence_engine=FakeStrategyIntelligenceEngine(),
        capital_allocation_engine=FakeCapitalAllocationEngine(),
        adaptive_position_sizing_engine=FakeAdaptivePositionSizingEngine(),
        portfolio_correlation_engine=FakePortfolioCorrelationEngine(),
        concentration_guard=FakeConcentrationGuard(),
        adaptive_exit_engine=FakeAdaptiveExitEngine(),
    )

    with pytest.raises(IntelligenceDecisionError):
        orchestrator.decide(_candidate())
