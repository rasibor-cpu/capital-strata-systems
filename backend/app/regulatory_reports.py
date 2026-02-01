"""
regulatory_reports.py
---------------------
Regulatory & Management Reporting Engine (GAAP / CBN / IFRS-ready)

Purpose:
- Produce end-of-day (EOD) regulatory returns
- Provide management-level summaries
- All figures derived strictly from immutable journal + reporting_store
- FX-normalized to base currency where required

Design principles:
- Read-only
- Deterministic
- Auditor-safe
- No balance mutation
"""

from datetime import date
from typing import Dict, Any, List

from backend.app.reporting_store import (
    get_all_journal_entries,
    get_journal_entries_for_year,
)
from backend.app.fx_daily_rates import get_fx_rate
from backend.app.credit_limits import aggregate_customer_exposure

BASE_CURRENCY = "USD"


# -----------------------------------
# DAILY TRIAL BALANCE (REGULATORY)
# -----------------------------------

def daily_trial_balance(report_date: str) -> Dict[str, Any]:
    """
    End-of-Day trial balance for regulators.
    """

    entries = get_all_journal_entries()

    total_dr = 0.0
    total_cr = 0.0
    lines = 0

    for e in entries:
        posted_at = str(e.get("posted_at", ""))
        if not posted_at.startswith(report_date):
            continue

        delta = float(e.get("delta", 0.0))
        side = e.get("side")

        if side == "DR":
            total_dr += abs(delta)
        elif side == "CR":
            total_cr += abs(delta)

        lines += 1

    total_dr = round(total_dr, 2)
    total_cr = round(total_cr, 2)

    return {
        "report": "daily_trial_balance",
        "report_date": report_date,
        "currency": BASE_CURRENCY,
        "lines": lines,
        "total_debit": total_dr,
        "total_credit": total_cr,
        "balanced": total_dr == total_cr,
        "gaap_assertion": "ΣDR = ΣCR"
    }


# -----------------------------------
# DAILY CUSTOMER EXPOSURE REPORT
# -----------------------------------

def daily_customer_exposure(
    customer_id: str,
    report_date: str
) -> Dict[str, Any]:
    """
    FX-normalized exposure per customer (One-Obligor view).
    """

    exposure = aggregate_customer_exposure(
        customer_id=customer_id,
        as_of_date=report_date
    )

    return {
        "report": "daily_customer_exposure",
        "report_date": report_date,
        "customer_id": customer_id,
        "base_currency": BASE_CURRENCY,
        "exposure": exposure
    }


# -----------------------------------
# FX POSITION SUMMARY (TREASURY)
# -----------------------------------

def fx_position_summary(report_date: str) -> Dict[str, Any]:
    """
    Treasury FX position summary by currency.
    """

    entries = get_all_journal_entries()
    positions: Dict[str, float] = {}

    for e in entries:
        posted_at = str(e.get("posted_at", ""))
        if not posted_at.startswith(report_date):
            continue

        currency = str(e.get("currency", "")).upper()
        delta = float(e.get("delta", 0.0))

        if currency not in positions:
            positions[currency] = 0.0

        positions[currency] += delta

    fx_summary: List[Dict[str, Any]] = []

    for ccy, bal in positions.items():
        fx_rate = 1.0
        if ccy != BASE_CURRENCY:
            fx_rate = get_fx_rate(ccy, BASE_CURRENCY, report_date)

        fx_summary.append({
            "currency": ccy,
            "position": round(bal, 2),
            "fx_rate_to_base": fx_rate,
            "position_base": round(bal * fx_rate, 2)
        })

    return {
        "report": "fx_position_summary",
        "report_date": report_date,
        "base_currency": BASE_CURRENCY,
        "positions": fx_summary
    }


# -----------------------------------
# MASTER EOD REGULATORY PACK
# -----------------------------------

def end_of_day_regulatory_pack(
    report_date: str,
    customer_ids: List[str]
) -> Dict[str, Any]:
    """
    Single callable to generate full EOD regulatory returns.
    """

    return {
        "report_pack": "EOD_REGULATORY",
        "report_date": report_date,
        "generated_on": date.today().isoformat(),
        "trial_balance": daily_trial_balance(report_date),
        "customers": [
            daily_customer_exposure(cid, report_date)
            for cid in customer_ids
        ],
        "fx_position": fx_position_summary(report_date),
        "note": "All figures derived from immutable journal. No manual adjustments."
    }
