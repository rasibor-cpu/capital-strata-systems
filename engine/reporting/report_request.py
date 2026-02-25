"""
engine/reporting/report_request.py

ReportRequest (FinCon-grade)
----------------------------
Standardizes:
- timeframe selection
- content/sections selection
- sign-off / provenance metadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, Dict, Any


@dataclass(frozen=True)
class ReportTimeframe:
    # One of these modes should be used
    mode: str = "range"  # "range" | "month_end" | "year_end"

    # For range mode (inclusive)
    start_date: Optional[str] = None  # "YYYY-MM-DD"
    end_date: Optional[str] = None    # "YYYY-MM-DD"

    # Optional unix timestamp bounds (seconds)
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None

    # For month_end/year_end helpers
    year: Optional[int] = None
    month: Optional[int] = None


@dataclass(frozen=True)
class ReportCaller:
    user_id: str = "UNKNOWN"
    display_name: str = "UNKNOWN"
    roles: Set[str] = field(default_factory=set)
    permissions: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ReportRequest:
    report_id: str

    # Who is printing (for sign-off/audit)
    caller: ReportCaller

    # Timeframe selection
    timeframe: ReportTimeframe = field(default_factory=ReportTimeframe)

    # What to include (explicit content control)
    # Example: {"summary", "top_reasons", "correlation", "sizing", "raw_counts", "signoff"}
    sections: Set[str] = field(default_factory=set)

    # Optional business scoping (for bank context)
    scope_id: Optional[str] = None
    account_ref: Optional[str] = None
    currency: Optional[str] = None
    target_user_id: Optional[str] = None

    # Any extra params
    params: Dict[str, Any] = field(default_factory=dict)