"""Canonical weighted Executive Score."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .executive_models import ExecutiveScorecard, ScoreCategory, TrafficLight


CATEGORY_WEIGHTS: dict[str, float] = {
    "financial_health": 0.16,
    "risk_health": 0.14,
    "execution_quality": 0.10,
    "capital_efficiency": 0.10,
    "operational_health": 0.10,
    "compliance": 0.10,
    "readiness": 0.08,
    "infrastructure": 0.07,
    "broker_health": 0.08,
    "data_freshness": 0.07,
}

CATEGORY_LABELS = {
    "financial_health": "Financial Health",
    "risk_health": "Risk Health",
    "execution_quality": "Execution Quality",
    "capital_efficiency": "Capital Efficiency",
    "operational_health": "Operational Health",
    "compliance": "Compliance",
    "readiness": "Readiness",
    "infrastructure": "Infrastructure",
    "broker_health": "Broker Health",
    "data_freshness": "Data Freshness",
}


class ExecutiveScorecardEngine:
    def calculate(
        self,
        category_inputs: Mapping[str, Any] | None,
    ) -> ExecutiveScorecard:
        values = dict(category_inputs or {})
        categories: list[ScoreCategory] = []
        for key, weight in CATEGORY_WEIGHTS.items():
            raw = values.get(key, 50.0)
            rationale = "canonical input"
            if isinstance(raw, Mapping):
                score = _score(raw.get("score"))
                rationale = str(raw.get("rationale") or rationale)
            else:
                score = _score(raw)
            categories.append(
                ScoreCategory(
                    key=key,
                    label=CATEGORY_LABELS[key],
                    score=score,
                    weight=weight,
                    status=status_for_score(score),
                    rationale=rationale,
                )
            )
        total_weight = sum(category.weight for category in categories)
        overall = (
            sum(category.score * category.weight for category in categories) / total_weight
            if total_weight
            else 0.0
        )
        return ExecutiveScorecard(
            overall_score=round(overall, 2),
            overall_status=status_for_score(overall),
            categories=tuple(categories),
            weights_total=round(total_weight, 6),
        )


def status_for_score(score: float) -> TrafficLight:
    return TrafficLight.GREEN if score >= 75 else TrafficLight.AMBER if score >= 50 else TrafficLight.RED


def _score(value: Any) -> float:
    try:
        return min(max(float(value), 0.0), 100.0)
    except (TypeError, ValueError):
        return 50.0


__all__ = [
    "CATEGORY_LABELS",
    "CATEGORY_WEIGHTS",
    "ExecutiveScorecardEngine",
    "status_for_score",
]
