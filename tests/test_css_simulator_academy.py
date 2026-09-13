from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.simulator import (
    AcademyScorer,
    ChallengeDefinition,
    ChallengeType,
    ForecastAssessment,
    SimulatedFill,
    SimulationEngine,
)


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def test_simulator_buy_sell_and_realized_pnl_are_deterministic():
    portfolio = SimulationEngine.create(Decimal("10000"), NOW)
    portfolio = SimulationEngine.apply_fill(
        portfolio,
        SimulatedFill("ABC", "BUY", Decimal("10"), Decimal("100"), NOW),
    )
    portfolio = SimulationEngine.apply_fill(
        portfolio,
        SimulatedFill("ABC", "SELL", Decimal("4"), Decimal("110"), NOW),
    )

    assert portfolio.cash == Decimal("9440")
    assert portfolio.positions["ABC"].quantity == Decimal("6")
    assert portfolio.positions["ABC"].average_cost == Decimal("100")
    assert portfolio.realized_pnl == Decimal("40")
    assert portfolio.equity == Decimal("10100")


def test_simulator_rejects_overspending_and_short_sell():
    portfolio = SimulationEngine.create(Decimal("100"), NOW)

    with pytest.raises(ValueError, match="insufficient simulated cash"):
        SimulationEngine.apply_fill(
            portfolio,
            SimulatedFill("ABC", "BUY", Decimal("2"), Decimal("60"), NOW),
        )

    with pytest.raises(ValueError, match="naked/short"):
        SimulationEngine.apply_fill(
            portfolio,
            SimulatedFill("ABC", "SELL", Decimal("1"), Decimal("60"), NOW),
        )


def test_mark_to_market_tracks_drawdown_without_real_execution():
    portfolio = SimulationEngine.create(Decimal("1000"), NOW)
    portfolio = SimulationEngine.apply_fill(
        portfolio,
        SimulatedFill("ABC", "BUY", Decimal("10"), Decimal("50"), NOW),
    )
    portfolio = SimulationEngine.mark_to_market(
        portfolio,
        {"ABC": Decimal("40")},
        NOW,
    )

    assert portfolio.equity == Decimal("900")
    assert portfolio.drawdown_pct == Decimal("0.1")


def test_academy_score_and_challenge_progress():
    portfolio = SimulationEngine.create(Decimal("1000"), NOW)
    portfolio = SimulationEngine.apply_fill(
        portfolio,
        SimulatedFill("ABC", "BUY", Decimal("10"), Decimal("50"), NOW),
    )
    portfolio = SimulationEngine.mark_to_market(
        portfolio,
        {"ABC": Decimal("60")},
        NOW,
    )

    score = AcademyScorer.score(
        portfolio,
        benchmark_return_pct=Decimal("0.05"),
        accepted_good_decisions=7,
        rejected_bad_decisions=1,
        total_decisions=10,
    )

    assert score.return_pct == Decimal("0.1")
    assert score.benchmark_excess_pct == Decimal("0.05")
    assert score.decision_quality_pct == Decimal("0.8")

    challenge = ChallengeDefinition(
        challenge_id="beat-benchmark",
        challenge_type=ChallengeType.BENCHMARK_OUTPERFORMANCE,
        target=Decimal("0.04"),
        minimum_observations=5,
    )
    progress = AcademyScorer.evaluate_challenge(challenge, score, observations=10)

    assert progress.complete is True
    assert AcademyScorer.badge_ids([progress]) == ("beat-benchmark",)


def test_forecast_requires_probabilities_not_certainty_claims():
    assessment = ForecastAssessment(
        as_of_utc=NOW,
        horizon="1 trading day",
        probability_up=Decimal("0.55"),
        probability_flat=Decimal("0.20"),
        probability_down=Decimal("0.25"),
        expected_low=Decimal("95"),
        expected_high=Decimal("108"),
        confidence=Decimal("0.64"),
        invalidation_condition="Break below 94 on confirmed volume.",
    )

    assert assessment.probability_up == Decimal("0.55")
    assert assessment.confidence == Decimal("0.64")

    with pytest.raises(ValueError, match="sum exactly to 1"):
        ForecastAssessment(
            as_of_utc=NOW,
            horizon="1 trading day",
            probability_up=Decimal("0.9"),
            probability_flat=Decimal("0.2"),
            probability_down=Decimal("0.1"),
            expected_low=Decimal("95"),
            expected_high=Decimal("108"),
            confidence=Decimal("0.5"),
            invalidation_condition="Invalid if support fails.",
        )


def test_simulator_surface_has_no_broker_execution_or_money_movement_methods():
    prohibited = {
        "place_order",
        "submit_order",
        "cancel_order",
        "replace_order",
        "withdraw",
        "transfer",
        "deposit",
        "fund_account",
        "move_money",
    }
    assert prohibited.isdisjoint(set(dir(SimulationEngine)))
