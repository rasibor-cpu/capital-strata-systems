from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

_MAJOR_EVENT_OFFSETS = [
    {"name": "FOMC", "offset_days": 3, "description": "Federal Reserve policy decision window."},
    {"name": "CPI", "offset_days": 5, "description": "Consumer inflation data release window."},
    {"name": "PPI", "offset_days": 8, "description": "Producer inflation data release window."},
    {"name": "NFP", "offset_days": 12, "description": "U.S. payrolls release window."},
    {"name": "GDP", "offset_days": 16, "description": "Gross domestic product release window."},
    {"name": "UNEMPLOYMENT_CLAIMS", "offset_days": 10, "description": "Initial claims and labor force release window."},
]


class EconomicCalendarProvider:
    def __init__(self, api_client: Any | None = None) -> None:
        self.api_client = api_client

    def _static_schedule(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = (now or datetime.now(timezone.utc)).replace(hour=12, minute=0, second=0, microsecond=0)
        schedule: list[dict[str, Any]] = []
        for item in _MAJOR_EVENT_OFFSETS:
            expected_date = now + timedelta(days=item["offset_days"])
            schedule.append({
                "name": item["name"],
                "expected_date": expected_date.isoformat(),
                "description": item["description"],
                "importance": "MAJOR",
                "source": "STATIC_SCHEDULE",
            })
        return schedule

    def get_today_events(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        today = now.date()
        return [event for event in self._static_schedule(now) if datetime.fromisoformat(event["expected_date"]).date() == today]

    def get_week_events(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        week_end = now + timedelta(days=7)
        return [
            event
            for event in self._static_schedule(now)
            if now.date() <= datetime.fromisoformat(event["expected_date"]).date() <= week_end.date()
        ]

    def is_major_event_today(self, now: datetime | None = None) -> bool:
        return len(self.get_today_events(now=now)) > 0


def get_today_events(now: datetime | None = None) -> list[dict[str, Any]]:
    return EconomicCalendarProvider().get_today_events(now=now)


def get_week_events(now: datetime | None = None) -> list[dict[str, Any]]:
    return EconomicCalendarProvider().get_week_events(now=now)


def is_major_event_today(now: datetime | None = None) -> bool:
    return EconomicCalendarProvider().is_major_event_today(now=now)
