"""
trial_balance.py
----------------
System-wide End-of-Day Trial Balance.

Purpose:
- Prove Σ DR = Σ CR
- Grouped by date and currency
- Derived strictly from immutable journal entries
- No balances mutated here (read-only control report)

This is a CORE BANKING CONTROL REPORT.
"""

from collections import defaultdict
from typing import Dict, Any, List
import datetime as _dt

# Journal registry is the single source of truth
from backend.app.ledger_registry import get_full_journal


def end_of_day_trial_balance(
    date_prefix: str | None = None
) -> Dict[str, Any]:
    """
    Compute system-wide trial balance.

    Args:
        date_prefix: YYYY-MM-DD (optional). Defaults to today.

    Returns:
        dict with totals per currency and integrity flag
    """

    if date_prefix is None:
        date_prefix = _dt.date.today().isoformat()

    journal = get_full_journal()

    per_currency = defaultdict(lambda: {
        "total_dr": 0.0,
        "total_cr": 0.0,
        "lines": 0
    })

    for entry in journal:
        posted_at = entry.get("posted_at", "")
        if not posted_at.startswith(date_prefix):
            continue

        currency = entry.get("currency", "UNKNOWN")
        side = entry.get("side")
        delta = float(entry.get("delta", 0.0))

        if side == "DR":
            per_currency[currency]["total_dr"] += abs(delta)
        elif side == "CR":
            per_currency[currency]["total_cr"] += abs(delta)

        per_currency[currency]["lines"] += 1

    results: List[Dict[str, Any]] = []
    integrity_ok = True

    for ccy, vals in sorted(per_currency.items()):
        balanced = round(vals["total_dr"], 2) == round(vals["total_cr"], 2)
        if not balanced:
            integrity_ok = False

        results.append({
            "currency": ccy,
            "total_dr": round(vals["total_dr"], 2),
            "total_cr": round(vals["total_cr"], 2),
            "lines": vals["lines"],
            "balanced": balanced
        })

    return {
        "report_type": "trial_balance",
        "date": date_prefix,
        "currencies": results,
        "integrity": "OK" if integrity_ok else "FAILED",
        "note": (
            "Trial balance derived from immutable journal entries. "
            "DR=CR enforced at posting; this report verifies integrity."
        )
    }


# Convenience CLI test
if __name__ == "__main__":
    import json
    print(json.dumps(end_of_day_trial_balance(), indent=2))
