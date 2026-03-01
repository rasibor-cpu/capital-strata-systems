"""
Capital Strata Systems (CSS)
Phase 24C – Period Control & Financial Year Rollover

Capabilities:
- Close financial period
- Reopen period (restricted use)
- Generate audit certificate
- Auto-create next financial year
- Immutable close enforcement
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

FINANCIAL_CALENDAR_FILE = Path("backend/app/config/financial_calendar.json")
PERIOD_AUDIT_FILE = Path("audit_logs/period_audit.jsonl")


def _load_calendar() -> Dict[str, Any]:
    if not FINANCIAL_CALENDAR_FILE.exists():
        raise FileNotFoundError("financial_calendar.json missing.")
    return json.loads(FINANCIAL_CALENDAR_FILE.read_text(encoding="utf-8"))


def _save_calendar(data: Dict[str, Any]) -> None:
    FINANCIAL_CALENDAR_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _append_audit_record(record: Dict[str, Any]) -> None:
    PERIOD_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PERIOD_AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def close_period(period: str, closed_by: str) -> Dict[str, Any]:
    """
    period format: YYYY-MM
    """

    calendar = _load_calendar()

    if period not in calendar["periods"]:
        raise ValueError(f"Unknown financial period: {period}")

    if calendar["periods"][period] == "CLOSED":
        raise ValueError(f"Period {period} already closed.")

    calendar["periods"][period] = "CLOSED"
    _save_calendar(calendar)

    certificate = {
        "period": period,
        "status": "CLOSED",
        "closed_by": closed_by,
        "closed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "certificate_id": f"PERIOD-{period}-CLOSE-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    }

    _append_audit_record(certificate)

    return certificate


def reopen_period(period: str, reopened_by: str) -> Dict[str, Any]:
    """
    Emergency use only. Should require high-level governance in UI layer.
    """

    calendar = _load_calendar()

    if period not in calendar["periods"]:
        raise ValueError(f"Unknown financial period: {period}")

    calendar["periods"][period] = "OPEN"
    _save_calendar(calendar)

    record = {
        "period": period,
        "status": "REOPENED",
        "reopened_by": reopened_by,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    _append_audit_record(record)

    return record


def rollover_financial_year(created_by: str) -> Dict[str, Any]:

    calendar = _load_calendar()

    fy = calendar["financial_year"]
    current_end = datetime.strptime(fy["end_date"], "%Y-%m-%d")

    next_year = current_end.year + 1
    new_start = datetime(next_year, 1, 1)
    new_end = datetime(next_year, 12, 31)

    new_periods = {
        f"{next_year}-{str(m).zfill(2)}": "OPEN"
        for m in range(1, 13)
    }

    calendar["financial_year"] = {
        "start_date": new_start.strftime("%Y-%m-%d"),
        "end_date": new_end.strftime("%Y-%m-%d"),
    }

    calendar["periods"] = new_periods

    _save_calendar(calendar)

    record = {
        "action": "FINANCIAL_YEAR_ROLLOVER",
        "new_financial_year": str(next_year),
        "created_by": created_by,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    _append_audit_record(record)

    return record