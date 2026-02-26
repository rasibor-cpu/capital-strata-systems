from __future__ import annotations

import json
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Set


def _repo_root() -> Path:
    # backend/app/business_calendar.py -> parents[2] is repo root
    return Path(__file__).resolve().parents[2]


def _holidays_path() -> Path:
    return _repo_root() / "backend" / "app" / "config" / "holidays.json"


def load_holidays() -> Set[str]:
    """
    Optional: backend/app/config/holidays.json
    Format: ["2026-01-01", "2026-03-29", ...]
    """
    p = _holidays_path()
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(x)[:10] for x in data}
    except Exception:
        pass
    return set()


def is_working_day(d: date, holidays: Set[str] | None = None) -> bool:
    holidays = holidays or set()
    iso = d.isoformat()
    # Weekend
    if d.weekday() >= 5:
        return False
    # Holiday
    if iso in holidays:
        return False
    return True


def previous_working_day(ref: date | None = None) -> date:
    ref = ref or datetime.utcnow().date()
    holidays = load_holidays()

    d = ref - timedelta(days=1)
    while not is_working_day(d, holidays):
        d -= timedelta(days=1)
    return d