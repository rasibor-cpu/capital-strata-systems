"""Deterministic executive forecast projection."""

from __future__ import annotations

from .executive_models import RunRateResult


def build_forecast(run_rate: RunRateResult) -> dict[str, float | str | bool]:
    return {
        "projected_year_end_profit": run_rate.projected_year_end_profit,
        "probability_of_meeting_target": run_rate.probability_of_meeting_target,
        "plan_variance": run_rate.variance,
        "status": run_rate.traffic_light.value,
        "method": "deterministic_run_rate_projection",
        "read_only": True,
        "execution_allowed": False,
    }


__all__ = ["build_forecast"]
