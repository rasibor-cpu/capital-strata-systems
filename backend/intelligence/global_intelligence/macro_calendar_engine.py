from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

_MAJOR_EVENTS = [
    {"name": "FOMC", "description": "Federal Reserve policy decision window."},
    {"name": "CPI", "description": "Consumer inflation data release window."},
    {"name": "PPI", "description": "Producer inflation data release window."},
    {"name": "NFP", "description": "U.S. payrolls release window."},
    {"name": "GDP", "description": "Gross domestic product release window."},
]


def get_upcoming_events() -> list[dict]:
    now = datetime.now(timezone.utc)
    upcoming = []
    for index, event in enumerate(_MAJOR_EVENTS, start=1):
        date = now + timedelta(days=7 * index)
        upcoming.append({
            "name": event["name"],
            "expected_date": date.isoformat() + "Z",
            "description": event["description"],
            "notes": "Static placeholder schedule for GIE v0.1.",
        })
    return upcoming


def is_high_risk_window(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    for event in get_upcoming_events():
        try:
            event_time = datetime.fromisoformat(event["expected_date"].replace("Z", ""))
        except ValueError:
            continue
        if abs((event_time - now).days) <= 3:
            return True
    return False