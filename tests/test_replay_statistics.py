from __future__ import annotations

import pytest

from backend.validation.replay_models import ReplayDecision
from backend.validation.replay_statistics import ReplayStatisticsError, build_replay_statistics


def _decision(timestamp: str, symbol: str, strategy: str, regime: str, decision: str, allocation_amount: float, confidence: float) -> ReplayDecision:
    return ReplayDecision(
        timestamp=timestamp,
        symbol=symbol,
        market_regime=regime,
        selected_strategy=strategy,
        allocation={"allocation_amount": allocation_amount, "allocation_weight": allocation_amount / 10000.0},
        position_size={"recommended_position_size": 100.0},
        risk_score=0.2,
        confidence=confidence,
        decision=decision,
        exit_plan={"action": "HOLD"},
        diagnostics={"source": "test"},
    )


def test_statistics_generation() -> None:
    stats = build_replay_statistics(
        [
            _decision("2026-06-24T10:00:00+00:00", "AAPL", "alpha", "TRENDING", "ALLOW", 3000.0, 0.9),
            _decision("2026-06-24T10:05:00+00:00", "MSFT", "beta", "TRENDING", "BLOCK", 1000.0, 0.4),
            _decision("2026-06-24T10:10:00+00:00", "EURUSD", "alpha", "RANGING", "REDUCE_SIZE", 500.0, 0.6),
        ]
    )

    assert stats.number_of_candidates == 3
    assert stats.number_of_approved_trades == 1
    assert stats.blocked_trades == 1
    assert stats.average_confidence == pytest.approx((0.9 + 0.4 + 0.6) / 3)
    assert stats.average_allocation == pytest.approx((3000.0 + 1000.0 + 500.0) / 3)
    assert stats.strategy_distribution == {"alpha": 2, "beta": 1}
    assert stats.regime_distribution == {"RANGING": 1, "TRENDING": 2}
    assert stats.decision_distribution == {"ALLOW": 1, "BLOCK": 1, "REDUCE_SIZE": 1}


def test_empty_history() -> None:
    stats = build_replay_statistics([])

    assert stats.number_of_candidates == 0
    assert stats.number_of_approved_trades == 0
    assert stats.blocked_trades == 0
    assert stats.average_confidence == 0.0
    assert stats.average_allocation == 0.0
    assert stats.strategy_distribution == {}
    assert stats.regime_distribution == {}
    assert stats.decision_distribution == {}


def test_corrupt_history() -> None:
    with pytest.raises(ReplayStatisticsError):
        build_replay_statistics([
            {
                "timestamp": "2026-06-24T10:00:00+00:00",
                "symbol": "AAPL",
                "market_regime": "TRENDING",
            }
        ])
