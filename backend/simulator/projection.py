from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Iterable

from .academy import Achievement, LessonProgress, RecommendationDecision
from .models import ChallengeProgress, ForecastAssessment, SimulatedPortfolio, SimulationScore


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def build_simulator_projection(
    *,
    portfolio: SimulatedPortfolio,
    score: SimulationScore,
    lessons: Iterable[LessonProgress] = (),
    decisions: Iterable[RecommendationDecision] = (),
    challenges: Iterable[ChallengeProgress] = (),
    achievements: Iterable[Achievement] = (),
    forecast: ForecastAssessment | None = None,
) -> dict:
    """Read-only projection suitable for API/mobile presentation.

    This function intentionally exposes no live broker identifiers, credentials,
    or executable order instructions.
    """

    position_rows = [
        {
            "symbol": position.symbol,
            "quantity": _decimal(position.quantity),
            "average_cost": _decimal(position.average_cost),
            "mark_price": _decimal(position.mark_price),
            "market_value": _decimal(position.market_value),
            "unrealized_pnl": _decimal(position.unrealized_pnl),
        }
        for position in sorted(portfolio.positions.values(), key=lambda p: p.symbol)
    ]

    payload = {
        "mode": "SIMULATION",
        "execution_allowed": False,
        "broker_execution_armed": False,
        "money_movement_allowed": False,
        "commercialization_attribution_allowed": False,
        "fee_entitlement_allowed": False,
        "live_trading_eligible": False,
        "portfolio": {
            "cash": _decimal(portfolio.cash),
            "market_value": _decimal(portfolio.market_value),
            "equity": _decimal(portfolio.equity),
            "realized_pnl": _decimal(portfolio.realized_pnl),
            "unrealized_pnl": _decimal(portfolio.unrealized_pnl),
            "total_pnl": _decimal(portfolio.total_pnl),
            "drawdown_pct": _decimal(portfolio.drawdown_pct),
            "as_of_utc": portfolio.as_of_utc.isoformat(),
            "positions": position_rows,
        },
        "score": {
            "return_pct": _decimal(score.return_pct),
            "max_drawdown_pct": _decimal(score.max_drawdown_pct),
            "benchmark_excess_pct": _decimal(score.benchmark_excess_pct),
            "decision_quality_pct": _decimal(score.decision_quality_pct),
            "capital_preserved": score.capital_preserved,
        },
        "lessons": [
            {
                "lesson_id": item.lesson_id,
                "status": item.status.value,
                "completed_at_utc": item.completed_at_utc.isoformat()
                if item.completed_at_utc
                else None,
            }
            for item in lessons
        ],
        "decisions": [
            {
                "decision_id": item.decision_id,
                "recommendation_id": item.recommendation_id,
                "action": item.action.value,
                "outcome": item.outcome.value,
                "recorded_at_utc": item.recorded_at_utc.isoformat(),
                "note": item.note,
            }
            for item in decisions
        ],
        "challenges": [
            {
                "challenge_id": item.challenge_id,
                "observations": item.observations,
                "metric_value": _decimal(item.metric_value),
                "complete": item.complete,
            }
            for item in challenges
        ],
        "achievements": [
            {
                "achievement_id": item.achievement_id,
                "awarded_at_utc": item.awarded_at_utc.isoformat(),
                "source": item.source,
            }
            for item in achievements
        ],
    }

    if forecast is not None:
        payload["forecast"] = {
            "horizon": forecast.horizon,
            "probability_up": _decimal(forecast.probability_up),
            "probability_flat": _decimal(forecast.probability_flat),
            "probability_down": _decimal(forecast.probability_down),
            "expected_low": _decimal(forecast.expected_low),
            "expected_high": _decimal(forecast.expected_high),
            "confidence": _decimal(forecast.confidence),
            "invalidation_condition": forecast.invalidation_condition,
            "as_of_utc": forecast.as_of_utc.isoformat(),
        }

    return payload
