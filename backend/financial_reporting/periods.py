"""Phase 177 — canonical reporting periods (timezone-aware UTC)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from backend.financial_reporting.models import ReportingPeriodType


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("reporting period timestamps must be timezone-aware")
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class ReportingPeriod:
    period_type: ReportingPeriodType
    start: datetime
    end: datetime
    timezone_name: str = "UTC"
    label: str = ""
    comparison_start: datetime | None = None
    comparison_end: datetime | None = None
    closed: bool = False

    def __post_init__(self) -> None:
        start = _ensure_utc(self.start)
        end = _ensure_utc(self.end)
        if end < start:
            raise ValueError("reporting period end must be >= start")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if self.comparison_start is not None:
            object.__setattr__(self, "comparison_start", _ensure_utc(self.comparison_start))
        if self.comparison_end is not None:
            object.__setattr__(self, "comparison_end", _ensure_utc(self.comparison_end))
        if not self.label:
            object.__setattr__(
                self,
                "label",
                f"{self.period_type.value} {start.date().isoformat()} → {end.date().isoformat()}",
            )

    @property
    def calendar_days(self) -> int:
        return max(1, (self.end.date() - self.start.date()).days + 1)

    def elapsed_days(self, *, as_of: datetime | None = None) -> int:
        now = _ensure_utc(as_of or datetime.now(timezone.utc))
        if now < self.start:
            return 0
        if now >= self.end or self.closed:
            return self.calendar_days
        return max(1, (now.date() - self.start.date()).days + 1)

    def remaining_days(self, *, as_of: datetime | None = None) -> int:
        return max(0, self.calendar_days - self.elapsed_days(as_of=as_of))

    def is_open(self, *, as_of: datetime | None = None) -> bool:
        if self.closed:
            return False
        now = _ensure_utc(as_of or datetime.now(timezone.utc))
        return self.start <= now <= self.end

    def to_display_timezone(self, tz_name: str) -> dict[str, str]:
        tz = ZoneInfo(tz_name)
        return {
            "timezone": tz_name,
            "start": self.start.astimezone(tz).isoformat(),
            "end": self.end.astimezone(tz).isoformat(),
        }

    def to_dict(self, *, as_of: datetime | None = None) -> dict[str, Any]:
        return {
            "period_type": self.period_type.value,
            "start": self.start.isoformat().replace("+00:00", "Z"),
            "end": self.end.isoformat().replace("+00:00", "Z"),
            "timezone": self.timezone_name,
            "label": self.label,
            "comparison_start": (
                self.comparison_start.isoformat().replace("+00:00", "Z")
                if self.comparison_start
                else None
            ),
            "comparison_end": (
                self.comparison_end.isoformat().replace("+00:00", "Z")
                if self.comparison_end
                else None
            ),
            "calendar_days": self.calendar_days,
            "elapsed_days": self.elapsed_days(as_of=as_of),
            "remaining_days": self.remaining_days(as_of=as_of),
            "closed": self.closed,
            "open": self.is_open(as_of=as_of),
        }


def build_period(
    period_type: ReportingPeriodType | str,
    start: datetime,
    end: datetime,
    *,
    label: str = "",
    timezone_name: str = "UTC",
    closed: bool = False,
    comparison_start: datetime | None = None,
    comparison_end: datetime | None = None,
) -> ReportingPeriod:
    ptype = (
        period_type
        if isinstance(period_type, ReportingPeriodType)
        else ReportingPeriodType(str(period_type).upper())
    )
    return ReportingPeriod(
        period_type=ptype,
        start=start,
        end=end,
        timezone_name=timezone_name,
        label=label,
        closed=closed,
        comparison_start=comparison_start,
        comparison_end=comparison_end,
    )


def month_to_date(as_of: datetime | None = None, *, timezone_name: str = "UTC") -> ReportingPeriod:
    now = _ensure_utc(as_of or datetime.now(timezone.utc))
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)
    return build_period(
        ReportingPeriodType.MONTHLY,
        start,
        end,
        label=f"{now.strftime('%Y-%m')} MTD",
        timezone_name=timezone_name,
        closed=False,
    )
