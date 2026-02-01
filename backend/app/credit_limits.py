"""
credit_limits.py
----------------
GAAP-aligned Credit / One-Obligor Limit Engine

Purpose:
- Aggregate all customer exposures across currencies
- Convert exposures using approved daily FX rates
- Enforce one-obligor / facility limits
- Produce auditable decisions (ALLOW / BLOCK)

Design principles:
- Read-only over journal (journal is immutable)
- FX-normalized to base currency (e.g. USD)
- Deterministic, reproducible, regulator-safe
"""

from datetime import date
from typing import Dict, List, Any

from backend.app.fx_daily_rates import get_fx_rate
from backend.app.ledger_registry import get_all_balances
from backend.app.customer_subledger import get_customer_accounts


# -----------------------------
# Configuration (policy layer)
# -----------------------------

BASE_CURRENCY = "USD"

# One-obligor limit per customer (can later be facility-driven)
DEFAULT_ONE_OBLIGOR_LIMIT = 1_000_000.00  # USD


# -----------------------------
# Core aggregation logic
# -----------------------------

def aggregate_customer_exposure(
    customer_id: str,
    as_of_date: str
) -> Dict[str, Any]:
    """
    Aggregate all balances for a customer across currencies
    and convert to base currency using daily FX rates.
    """

    accounts = get_customer_accounts(customer_id)
    balances = get_all_balances(as_of_date)

    exposure_lines: List[Dict[str, Any]] = []
    total_exposure_base = 0.0

    for acct in accounts:
        sub_account_id = acct["sub_account_id"]
        currency = acct["currency"]

        bal = balances.get(sub_account_id, 0.0)

        if bal == 0:
            continue

        fx_rate = 1.0
        if currency != BASE_CURRENCY:
            fx_rate = get_fx_rate(currency, BASE_CURRENCY, as_of_date)

        exposure_base = round(bal * fx_rate, 2)
        total_exposure_base += exposure_base

        exposure_lines.append({
            "sub_account_id": sub_account_id,
            "currency": currency,
            "balance": bal,
            "fx_rate": fx_rate,
            "exposure_base": exposure_base
        })

    return {
        "customer_id": customer_id,
        "as_of_date": as_of_date,
        "base_currency": BASE_CURRENCY,
        "lines": exposure_lines,
        "total_exposure": round(total_exposure_base, 2)
    }


# -----------------------------
# Limit enforcement
# -----------------------------

def check_one_obligor_limit(
    customer_id: str,
    as_of_date: str,
    limit: float = DEFAULT_ONE_OBLIGOR_LIMIT
) -> Dict[str, Any]:
    """
    Enforce one-obligor limit.
    """

    agg = aggregate_customer_exposure(customer_id, as_of_date)
    exposure = agg["total_exposure"]

    ok = exposure <= limit

    return {
        "check": "one_obligor_limit",
        "customer_id": customer_id,
        "as_of_date": as_of_date,
        "limit": round(limit, 2),
        "exposure": exposure,
        "headroom": round(limit - exposure, 2),
        "decision": "ALLOW" if ok else "BLOCK",
        "reason": (
            "Within approved one-obligor limit"
            if ok else
            "One-obligor limit breached"
        ),
        "details": agg
    }


# -----------------------------
# Orchestration hook
# -----------------------------

def evaluate_credit_position(
    customer_id: str,
    as_of_date: str | None = None
) -> Dict[str, Any]:
    """
    Entry point used by posting / approval engine.
    """

    if as_of_date is None:
        as_of_date = date.today().isoformat()

    result = check_one_obligor_limit(customer_id, as_of_date)

    return {
        "engine": "credit_limits",
        "timestamp": date.today().isoformat(),
        "result": result
    }
