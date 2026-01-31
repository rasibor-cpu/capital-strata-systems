"""
ageing.py — Ageing Buckets for Suspense/Sundry/Unsettled Transactions
--------------------------------------------------------------------
Requirement (authoritative buckets, where T = initial entry date):
- T+1 day
- T+3 days
- T+7 days
- T+30 days
- T+180 days
- T+>180 days

This module provides deterministic bucket assignment for any record that has:
- an initial date (T)
- an as-of date (report date)
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Dict, Any


BUCKETS = (
    "T+1 day",
    "T+3 days",
    "T+7 days",
    "T+30 days",
    "T+180 days",
    "T+>180 days",
)


def _to_date(d: Any) -> date:
    """
    Accepts:
    - date
    - datetime
    - ISO 8601 string (YYYY-MM-DD or full timestamp)
    """
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        # Try YYYY-MM-DD first, else datetime ISO
        try:
            return datetime.strptime(d[:10], "%Y-%m-%d").date()
        except Exception:
            # last resort: attempt full ISO parse by stripping Z if present
            ds = d.replace("Z", "+00:00")
            return datetime.fromisoformat(ds).date()
    raise ValueError("Unsupported date format")


def age_days(t_date: Any, as_of: Optional[Any] = None) -> int:
    """
    Returns full days elapsed from T to as_of.
    If as_of is None, uses today (UTC date).
    """
    t = _to_date(t_date)
    a = _to_date(as_of) if as_of is not None else datetime.utcnow().date()
    delta = (a - t).days
    return max(delta, 0)


def bucket_for_days(days: int) -> str:
    """
    Deterministic mapping to the required buckets.
    """
    if days <= 1:
        return "T+1 day"
    if days <= 3:
        return "T+3 days"
    if days <= 7:
        return "T+7 days"
    if days <= 30:
        return "T+30 days"
    if days <= 180:
        return "T+180 days"
    return "T+>180 days"


def bucket_for_date(t_date: Any, as_of: Optional[Any] = None) -> str:
    """
    Computes bucket from T date to as_of.
    """
    d = age_days(t_date, as_of=as_of)
    return bucket_for_days(d)


@dataclass
class AgeingResult:
    t_date: str
    as_of: str
    days: int
    bucket: str


def classify(t_date: Any, as_of: Optional[Any] = None) -> AgeingResult:
    """
    Convenience wrapper that returns structured result.
    """
    t = _to_date(t_date)
    a = _to_date(as_of) if as_of is not None else datetime.utcnow().date()
    days = age_days(t, a)
    bucket = bucket_for_days(days)
    return AgeingResult(
        t_date=t.isoformat(),
        as_of=a.isoformat(),
        days=days,
        bucket=bucket,
    )


def bucket_counts() -> Dict[str, int]:
    """
    Useful for initializing report aggregators.
    """
    return {b: 0 for b in BUCKETS}
