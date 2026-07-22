"""Deterministic executive alert projection."""

from __future__ import annotations

from .executive_models import ExecutiveScorecard, RunRateResult, TrafficLight


def build_executive_alerts(
    scorecard: ExecutiveScorecard,
    run_rate: RunRateResult,
) -> tuple[dict[str, str], ...]:
    alerts: list[dict[str, str]] = []
    for category in scorecard.categories:
        if category.status == TrafficLight.RED:
            alerts.append(
                {
                    "severity": "CRITICAL",
                    "category": category.key,
                    "message": f"{category.label} is RED at {category.score:.1f}.",
                }
            )
    if run_rate.traffic_light == TrafficLight.RED:
        alerts.append(
            {
                "severity": "WARNING",
                "category": "run_rate",
                "message": "Projected year-end profit is materially below target.",
            }
        )
    return tuple(alerts)


__all__ = ["build_executive_alerts"]
