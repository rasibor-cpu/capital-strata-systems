"""
engine/reporting/trial_balance.py

Trial Balance – Phase 17 (Gateway-Compatible)
---------------------------------------------
Callable from report_printer using as_of_date keyword.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, List


def _parse_ymd(s: str) -> str:
    datetime.strptime(s, "%Y-%m-%d")
    return s


def _display_header(*, title: str, ledger_date: str) -> str:
    bar = "=" * 78
    return (
        f"{title}\n"
        f"LEDGER DATE (AS AT TRANSACTION DATE): {ledger_date}\n"
        f"{bar}\n"
    )


def generate_trial_balance(
    *,
    as_of_date: Optional[str] = None,
    ledger_date: Optional[str] = None,
    date: Optional[str] = None,
    role: str = "",
    filters: Optional[Dict[str, Any]] = None,
    sections: Optional[List[str]] = None,
    **_ignored: Any,
) -> Dict[str, Any]:

    filters = filters or {}
    sections = sections or []

    raw = as_of_date or ledger_date or date
    if not raw:
        raw = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        ledger_date_norm = _parse_ymd(str(raw))
    except Exception:
        raise ValueError("trial_balance: date must be YYYY-MM-DD (e.g., 2026-02-26)")

    header = _display_header(title="TRIAL BALANCE", ledger_date=ledger_date_norm)

    body = (
        "STATUS: WIRED (gateway-compatible)\n"
        "NEXT: Load Chart of Accounts and compute balances.\n"
    )

    return {
        "ok": True,
        "report_name": "trial_balance",
        "ledger_date": ledger_date_norm,
        "role": (role or "").strip().upper(),
        "content": header + body,
    }


def run_trial_balance(*, as_of_date: Optional[str] = None, **kwargs: Any):
    return generate_trial_balance(as_of_date=as_of_date, **kwargs)


def print_trial_balance(*, as_of_date: Optional[str] = None, **kwargs: Any):
    return generate_trial_balance(as_of_date=as_of_date, **kwargs)