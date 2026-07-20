"""Phase 177 — profitability run-rate vs period target (Decimal, traffic-light)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from backend.financial_reporting.models import TrafficLight, money, ratio, serialize_decimal
from backend.financial_reporting.periods import ReportingPeriod


@dataclass(frozen=True)
class ProfitabilityRunRateConfig:
    """Configurable amber/red thresholds as multiples of actual daily run rate."""

    amber_max_multiple: Decimal = Decimal("1.50")  # required ≤ 1.5× actual → AMBER
    red_multiple: Decimal = Decimal("1.50")  # required > 1.5× actual → RED
    green_buffer_ratio: Decimal = Decimal("0.05")  # projected ≥ target × (1-buffer) → GREEN


@dataclass(frozen=True)
class ProfitabilityRunRate:
    target_profit: Decimal | None
    actual_net_profit: Decimal | None
    remaining_profit_required: Decimal | None
    elapsed_days: int | None
    remaining_days: int | None
    actual_daily_run_rate: Decimal | None
    required_daily_run_rate: Decimal | None
    projected_period_end_profit: Decimal | None
    projected_target_variance: Decimal | None
    percentage_of_target_achieved: Decimal | None
    traffic_light: TrafficLight
    confidence_status: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        s = serialize_decimal
        return {
            "target_profit": s(self.target_profit),
            "actual_net_profit": s(self.actual_net_profit),
            "remaining_profit_required": s(self.remaining_profit_required),
            "elapsed_days": self.elapsed_days,
            "remaining_days": self.remaining_days,
            "actual_daily_run_rate": s(self.actual_daily_run_rate),
            "required_daily_run_rate": s(self.required_daily_run_rate),
            "projected_period_end_profit": s(self.projected_period_end_profit),
            "projected_target_variance": s(self.projected_target_variance),
            "percentage_of_target_achieved": s(self.percentage_of_target_achieved),
            "traffic_light": self.traffic_light.value,
            "confidence_status": self.confidence_status,
            "warnings": list(self.warnings),
        }


def generate_profitability_run_rate(
    *,
    actual_net_profit: Decimal | None,
    target_profit: Decimal | None,
    period: ReportingPeriod | None,
    as_of: datetime | None = None,
    config: ProfitabilityRunRateConfig | None = None,
) -> ProfitabilityRunRate:
    cfg = config or ProfitabilityRunRateConfig()
    warnings: list[str] = []

    if period is None or target_profit is None or actual_net_profit is None:
        return ProfitabilityRunRate(
            target_profit=target_profit,
            actual_net_profit=actual_net_profit,
            remaining_profit_required=None,
            elapsed_days=period.elapsed_days(as_of=as_of) if period else None,
            remaining_days=period.remaining_days(as_of=as_of) if period else None,
            actual_daily_run_rate=None,
            required_daily_run_rate=None,
            projected_period_end_profit=None,
            projected_target_variance=None,
            percentage_of_target_achieved=None,
            traffic_light=TrafficLight.NOT_AVAILABLE,
            confidence_status="NOT_AVAILABLE",
            warnings=("target, dates, or required financial inputs are missing",),
        )

    elapsed = period.elapsed_days(as_of=as_of)
    remaining = period.remaining_days(as_of=as_of)
    target = money(target_profit)
    actual = money(actual_net_profit)

    remaining_required = money(target - actual)
    # If already exceeded a positive target (or beat a negative target), clamp display run-rate
    target_met = (target >= 0 and actual >= target) or (target < 0 and actual <= target)

    pct = None
    if target != 0:
        pct = ratio(actual / target)
    elif actual == 0:
        pct = ratio(1)
    else:
        pct = None
        warnings.append("target_profit is zero; percentage_of_target_achieved undefined")

    actual_daily = None
    if elapsed > 0:
        actual_daily = money(actual / Decimal(elapsed))

    required_daily = None
    if target_met:
        required_daily = money(0)
    elif remaining > 0:
        required_daily = money(remaining_required / Decimal(remaining))
    else:
        # Period ended — required run rate not meaningful as a forward rate
        required_daily = money(0)
        if not target_met:
            warnings.append("remaining_days=0 and target not achieved")

    projected = None
    if actual_daily is not None:
        projected = money(actual + actual_daily * Decimal(remaining))
    elif remaining == 0:
        projected = actual

    variance = None
    if projected is not None:
        variance = money(projected - target)

    # Traffic light
    if target_met:
        light = TrafficLight.GREEN
        confidence = "ACHIEVED"
    elif projected is not None and variance is not None:
        buffer = money(abs(target) * cfg.green_buffer_ratio)
        if variance >= money(0) or (target >= 0 and projected >= money(target - buffer)):
            light = TrafficLight.GREEN
            confidence = "ON_TRACK"
        elif actual_daily is not None and required_daily is not None:
            if actual_daily == 0:
                light = TrafficLight.RED if required_daily > 0 else TrafficLight.AMBER
                confidence = "STRESSED" if light == TrafficLight.RED else "AT_RISK"
            else:
                multiple = abs(required_daily / actual_daily) if actual_daily != 0 else Decimal("999")
                if multiple <= cfg.amber_max_multiple:
                    light = TrafficLight.AMBER
                    confidence = "AT_RISK"
                else:
                    light = TrafficLight.RED
                    confidence = "STRESSED"
        else:
            light = TrafficLight.AMBER
            confidence = "AT_RISK"
    else:
        light = TrafficLight.NOT_AVAILABLE
        confidence = "NOT_AVAILABLE"

    # Display remaining_required: preserve true amount even when negative (over-achievement)
    display_remaining = remaining_required
    if target_met and remaining_required < 0:
        # Do not show a misleading negative "required" run rate path; keep overshoot in remaining
        pass

    return ProfitabilityRunRate(
        target_profit=target,
        actual_net_profit=actual,
        remaining_profit_required=display_remaining,
        elapsed_days=elapsed,
        remaining_days=remaining,
        actual_daily_run_rate=actual_daily,
        required_daily_run_rate=required_daily,
        projected_period_end_profit=projected,
        projected_target_variance=variance,
        percentage_of_target_achieved=pct,
        traffic_light=light,
        confidence_status=confidence,
        warnings=tuple(warnings),
    )
