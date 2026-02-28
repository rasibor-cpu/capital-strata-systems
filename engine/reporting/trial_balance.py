"""
engine/reporting/trial_balance.py

Trial Balance – Phase 17 (Gateway-Compatible)
---------------------------------------------
Key goal:
- Must be callable from report_printer/report_center using as_of_date=
- Backward compatible if older callers pass date= / ledger_date=
- Fail-closed with clear error messages
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, List


def _parse_ymd(s: str) -> str:
    # normalize + validate YYYY-MM-DD
    datetime.strptime(s, "%Y-%m-%d")
    return s


def _display_header(*, title: str, ledger_date: str) -> str:
    # very legible date at top
    bar = "=" * 78
    return (
        f"{title}\n"
        f"LEDGER DATE (AS AT TRANSACTION DATE): {ledger_date}\n"
        f"{bar}\n"
    )


def generate_trial_balance(
    *,
    # ✅ primary gateway kw
    as_of_date: Optional[str] = None,
    # ✅ backward-compat aliases
    ledger_date: Optional[str] = None,
    date: Optional[str] = None,
    # ✅ common gateway kwargs
    role: str = "",
    filters: Optional[Dict[str, Any]] = None,
    sections: Optional[List[str]] = None,
    # ✅ tolerate extra kwargs from generic dispatchers
    **_ignored: Any,
) -> Dict[str, Any]:
    """
    Returns dict { ok, report_name, ledger_date, content, notes? }
    content is printable text (string).
    """

    filters = filters or {}
    sections = sections or []

    # Determine ledger date (transaction-date “as at”)
    raw = as_of_date or ledger_date or date
    if not raw:
        # default to today (still deterministic formatting)
        raw = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        ledger_date_norm = _parse_ymd(str(raw))
    except Exception:
        raise ValueError("trial_balance: date must be YYYY-MM-DD (e.g., 2026-02-26)")

    # ------------------------------------------------------------
    # NOTE:
    # We are NOT inventing a COA here (you requested bank-grade COA
    # incl. interbranch). That must be sourced from your COA config
    # file(s). This module should load the COA and print balances
    # by account class.
    #
    # For now, we return a clear stub so the gateway wiring is fixed
    # and we can proceed to COA-backed balances next.
    # ------------------------------------------------------------

    header = _display_header(title="TRIAL BALANCE", ledger_date=ledger_date_norm)

    body = (
        "STATUS: WIRED (gateway-compatible)\n"
        "NEXT: Load Chart of Accounts + interbranch ledgers and compute balances.\n"
        "\n"
        "Required (per your spec):\n"
        "- All internal GLs use 000 prefix (internal marker)\n"
        "- Include typical bank/trading COA groups + interbranch ledgers\n"
        "- Print must be audit-friendly and reproducible\n"
    )

    return {
        "ok": True,
        "report_name": "trial_balance",
        "ledger_date": ledger_date_norm,
        "role": (role or "").strip().upper(),
        "content": header + body,
    }