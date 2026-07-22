"""Deterministic profitability and target run-rate engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .business_calendar import BusinessCalendar
from .executive_models import RunRateResult, TrafficLight


@dataclass(frozen=True)
class RunRateInputs:
    annual_target: float
    quarterly_target: float
    monthly_target: float
    current_profit: float
    current_date: date
    trading_days: int | None = None


class ExecutiveRunRateEngine:
    def calculate(
        self,
        inputs: RunRateInputs,
        *,
        calendar: BusinessCalendar | None = None,
    ) -> RunRateResult:
        active_calendar = calendar or BusinessCalendar.for_year(inputs.current_date.year)
        year_start = date(inputs.current_date.year, 1, 1)
        year_end = date(inputs.current_date.year, 12, 31)
        elapsed = active_calendar.business_days_between(year_start, inputs.current_date)
        remaining_start = min(inputs.current_date + timedelta(days=1), year_end)
        remaining = active_calendar.business_days_between(remaining_start, year_end)
        total_days = int(inputs.trading_days or (elapsed + remaining))
        if total_days < elapsed:
            total_days = elapsed
        remaining = max(total_days - elapsed, 0)

        remaining_profit = max(float(inputs.annual_target) - float(inputs.current_profit), 0.0)
        daily_required = _safe_ratio(remaining_profit, remaining)
        weekly_required = daily_required * min(5, remaining)
        months_remaining = max(13 - inputs.current_date.month, 1)
        monthly_required = remaining_profit / months_remaining
        run_rate = _safe_ratio(float(inputs.current_profit), elapsed)
        projected = run_rate * total_days
        variance = float(inputs.current_profit) - (
            float(inputs.annual_target) * _safe_ratio(elapsed, total_days)
        )
        probability = _probability(
            target=float(inputs.annual_target),
            current=float(inputs.current_profit),
            projected=projected,
            elapsed=elapsed,
            total=total_days,
        )
        traffic = (
            TrafficLight.AMBER
            if inputs.annual_target <= 0
            else TrafficLight.GREEN
            if projected >= inputs.annual_target
            else TrafficLight.AMBER
            if projected >= inputs.annual_target * 0.85
            else TrafficLight.RED
        )
        commentary = _commentary(
            traffic=traffic,
            projected=projected,
            target=float(inputs.annual_target),
            variance=variance,
            required_daily=daily_required,
        )
        return RunRateResult(
            annual_target=round(float(inputs.annual_target), 2),
            quarterly_target=round(float(inputs.quarterly_target), 2),
            monthly_target=round(float(inputs.monthly_target), 2),
            current_profit=round(float(inputs.current_profit), 2),
            elapsed_trading_days=elapsed,
            remaining_trading_days=remaining,
            required_daily_profit=round(daily_required, 2),
            required_weekly_profit=round(weekly_required, 2),
            required_monthly_profit=round(monthly_required, 2),
            run_rate=round(run_rate, 2),
            variance=round(variance, 2),
            projected_year_end_profit=round(projected, 2),
            probability_of_meeting_target=round(probability, 4),
            traffic_light=traffic,
            commentary=commentary,
        )


def _safe_ratio(numerator: float, denominator: int | float) -> float:
    return numerator / float(denominator) if denominator else 0.0


def _probability(*, target: float, current: float, projected: float, elapsed: int, total: int) -> float:
    if target <= 0:
        return 0.0
    if current >= target:
        return 1.0
    trajectory = projected / target
    evidence_weight = min(max(_safe_ratio(elapsed, total), 0.05), 1.0)
    probability = 0.5 + ((trajectory - 1.0) * 0.75 * evidence_weight)
    return min(max(probability, 0.01), 0.99)


def _commentary(
    *,
    traffic: TrafficLight,
    projected: float,
    target: float,
    variance: float,
    required_daily: float,
) -> str:
    if traffic == TrafficLight.GREEN:
        return (
            "Profitability is on or above the annual objective; the projected "
            f"year-end result is {projected:,.2f} against a target of {target:,.2f}."
        )
    if traffic == TrafficLight.AMBER:
        return (
            "Run rate is moderately below the annual objective. "
            f"The remaining plan requires {required_daily:,.2f} per trading day."
        )
    return (
        "Run rate remains below the annual objective. "
        f"Plan variance is {variance:,.2f} and the remaining requirement is "
        f"{required_daily:,.2f} per trading day."
    )


__all__ = ["ExecutiveRunRateEngine", "RunRateInputs"]
