from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeLadderingError(ValueError):
    """Raised when paper expiry laddering cannot be evaluated."""


@dataclass(frozen=True)
class ExpiryLadderReport:
    ladder_type: str
    ladder_quality_score: float
    expiry_distribution: dict[str, float]
    weekly_count: int
    monthly_count: int
    mixed_ladder: bool
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ladder_type": self.ladder_type,
            "ladder_quality_score": self.ladder_quality_score,
            "expiry_distribution": self.expiry_distribution,
            "weekly_count": self.weekly_count,
            "monthly_count": self.monthly_count,
            "mixed_ladder": self.mixed_ladder,
            **SAFE_FLAGS,
        }


class OptionsIncomeLadderBuilder:
    def build(self, allocations: Sequence[Mapping[str, Any]]) -> ExpiryLadderReport:
        total = sum(float(row.get("collateral", 0.0) or 0.0) for row in allocations)
        expiries: dict[str, float] = {}
        weekly = 0
        monthly = 0
        for row in allocations:
            expiry = str(row.get("expiry") or "").strip()
            _date(expiry)
            expiries[expiry] = expiries.get(expiry, 0.0) + float(row.get("collateral", 0.0) or 0.0)
            day = datetime.fromisoformat(expiry).day
            if day <= 7 or day >= 24:
                weekly += 1
            else:
                monthly += 1
        distribution = {key: round(value / total, 8) for key, value in sorted(expiries.items())} if total > 0 else {}
        if weekly and monthly:
            ladder_type = "MIXED"
        elif weekly:
            ladder_type = "WEEKLY"
        elif monthly:
            ladder_type = "MONTHLY"
        else:
            ladder_type = "EMPTY"
        max_bucket = max(distribution.values(), default=0.0)
        quality = round(max(0.0, min(100.0, (1.0 - max_bucket) * 100.0 + min(len(distribution), 4) * 5.0)), 6)
        return ExpiryLadderReport(
            ladder_type=ladder_type,
            ladder_quality_score=quality,
            expiry_distribution=distribution,
            weekly_count=weekly,
            monthly_count=monthly,
            mixed_ladder=ladder_type == "MIXED",
        )


def _date(value: str) -> None:
    try:
        datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise OptionsIncomeLadderingError("Invalid ladder expiry") from exc


__all__ = ["ExpiryLadderReport", "OptionsIncomeLadderBuilder", "OptionsIncomeLadderingError"]
