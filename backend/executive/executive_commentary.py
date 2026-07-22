"""Deterministic, non-LLM executive commentary rules."""

from __future__ import annotations

from collections.abc import Mapping

from .executive_models import ExecutiveScorecard, MetricValue, RunRateResult, TrafficLight


class ExecutiveCommentaryEngine:
    def generate(
        self,
        *,
        metrics: Mapping[str, MetricValue],
        scorecard: ExecutiveScorecard,
        run_rate: RunRateResult,
    ) -> tuple[str, ...]:
        comments: list[str] = []
        net_profit = _value(metrics, "net_profit")
        capital_efficiency = _value(metrics, "capital_efficiency")
        realized = _value(metrics, "realized_pnl")
        utilization = _value(metrics, "capital_utilization")

        if net_profit > 0 and capital_efficiency > 0:
            comments.append(
                "Revenue and profit performance remain positive while capital efficiency improved."
            )
        elif net_profit < 0:
            comments.append(
                "Net profitability is negative and requires management attention despite the read-only operating posture."
            )

        if run_rate.traffic_light == TrafficLight.GREEN:
            comments.append(
                "The current profitability run rate is on or above the annual objective."
            )
        elif run_rate.traffic_light == TrafficLight.AMBER:
            comments.append(
                "Run rate is moderately below plan and should be monitored against the required daily profit."
            )
        else:
            comments.append(
                "Run rate remains below the annual objective because realized gains have not kept pace with the plan."
            )

        if realized <= 0 and utilization > 0.5:
            comments.append(
                "Realized gains have slowed despite increased capital deployment."
            )

        red_categories = [
            category.label
            for category in scorecard.categories
            if category.status == TrafficLight.RED
        ]
        if red_categories:
            comments.append(
                "Executive attention is required for " + ", ".join(red_categories[:3]) + "."
            )
        elif scorecard.overall_status == TrafficLight.GREEN:
            comments.append(
                "The weighted Executive Score indicates a stable enterprise operating position."
            )

        return tuple(comments or ("Executive evidence is insufficient for directional commentary.",))


def _value(metrics: Mapping[str, MetricValue], key: str) -> float:
    metric = metrics.get(key)
    try:
        return float(metric.value) if metric and metric.value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


__all__ = ["ExecutiveCommentaryEngine"]
