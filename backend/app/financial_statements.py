"""
financial_statements.py
-----------------------
GAAP-compliant Financial Statements Engine.

Uses reporting_store as the read-only interface to the immutable journal.

GAAP principles enforced:
- Income Statement (P&L) resets every financial year (INCOME/EXPENSE only for that year)
- Balance Sheet carries forward (ASSET/LIABILITY/EQUITY cumulative up to year-end)
- FX normalization to base currency is supported through fx_daily_rates when enabled

Notes:
- This file is READ-ONLY reporting logic.
- No postings, no balance mutation.
"""

from datetime import datetime
from typing import Dict, Any

from backend.app.reporting_store import get_all_journal_entries, get_journal_entries_for_year

# If you already have FX module and want FX-normalized statements, keep this import.
# If fx_daily_rates doesn't yet expose get_fx_rate_to_base, we fall back to 1.0.
try:
    from backend.app.fx_daily_rates import get_fx_rate_to_base  # type: ignore
except Exception:
    def get_fx_rate_to_base(currency: str, date_iso: str, base_currency: str = "USD") -> float:  # type: ignore
        return 1.0

BASE_CURRENCY = "USD"

# Ledger-type mapping should come from your account type catalog.
# We expect ACCOUNT_TYPE_MAP[account_type_code]["ledger_type"] in:
# ASSET, LIABILITY, EQUITY, INCOME, EXPENSE
try:
    from backend.app.account_types import ACCOUNT_TYPE_MAP  # type: ignore
except Exception:
    ACCOUNT_TYPE_MAP = {}  # graceful fallback


def _ledger_type_for_account_type(account_type_code: str) -> str:
    cfg = ACCOUNT_TYPE_MAP.get(account_type_code, {})
    return str(cfg.get("ledger_type", "")).upper()


def generate_profit_and_loss(financial_year: int) -> Dict[str, Any]:
    """
    Income Statement for a single financial year.
    Only INCOME and EXPENSE lines from that year are included.
    """
    entries = get_journal_entries_for_year(financial_year)

    income = 0.0
    expense = 0.0

    for e in entries:
        acct_type = str(e.get("account_type_code", "")).upper()
        ledger_type = _ledger_type_for_account_type(acct_type)

        posted_at = str(e.get("posted_at", ""))
        date_iso = posted_at[:10] if len(posted_at) >= 10 else f"{financial_year}-01-01"

        ccy = str(e.get("currency", "")).upper()
        fx = float(get_fx_rate_to_base(ccy, date_iso, BASE_CURRENCY))
        delta_base = float(e.get("delta", 0.0)) * fx

        # Convention used in your engine:
        # DR entries are +delta, CR entries are -delta (from ledger_registry).
        # For INCOME, credits increase income => negative delta => add absolute.
        if ledger_type == "INCOME":
            income += (-delta_base)
        elif ledger_type == "EXPENSE":
            expense += (delta_base)

    net_profit = round(income - expense, 2)

    return {
        "statement": "profit_and_loss",
        "financial_year": financial_year,
        "base_currency": BASE_CURRENCY,
        "income": round(income, 2),
        "expense": round(expense, 2),
        "net_profit": net_profit,
        "gaap_note": "P&L accounts reset annually; only year movements included."
    }


def generate_balance_sheet(financial_year: int) -> Dict[str, Any]:
    """
    Balance Sheet snapshot as at year-end.
    Includes cumulative movements up to and including financial_year for BS accounts.
    """
    entries = get_all_journal_entries()

    assets = 0.0
    liabilities = 0.0
    equity = 0.0

    for e in entries:
        posted_at = str(e.get("posted_at", ""))
        if len(posted_at) < 4:
            continue

        try:
            yr = int(posted_at[:4])
        except Exception:
            continue

        if yr > financial_year:
            continue  # carry-forward up to year-end only

        acct_type = str(e.get("account_type_code", "")).upper()
        ledger_type = _ledger_type_for_account_type(acct_type)

        # Only BS ledgers belong here
        if ledger_type not in ("ASSET", "LIABILITY", "EQUITY"):
            continue

        date_iso = posted_at[:10] if len(posted_at) >= 10 else f"{yr}-01-01"
        ccy = str(e.get("currency", "")).upper()
        fx = float(get_fx_rate_to_base(ccy, date_iso, BASE_CURRENCY))
        delta_base = float(e.get("delta", 0.0)) * fx

        # Asset debits increase assets (+delta)
        if ledger_type == "ASSET":
            assets += delta_base
        # Liabilities and Equity normally increase on credit (-delta),
        # so we invert sign to keep positive presentation.
        elif ledger_type == "LIABILITY":
            liabilities += (-delta_base)
        elif ledger_type == "EQUITY":
            equity += (-delta_base)

    assets = round(assets, 2)
    liabilities = round(liabilities, 2)
    equity = round(equity, 2)

    return {
        "statement": "balance_sheet",
        "financial_year": financial_year,
        "base_currency": BASE_CURRENCY,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "balanced": round(assets - (liabilities + equity), 2) == 0.0,
        "gaap_assertion": "Assets = Liabilities + Equity (presentation values)."
    }


def retained_earnings_rollforward(financial_year: int) -> Dict[str, Any]:
    """
    Retained earnings roll-forward (simplified).
    Opening retained earnings is carried forward; net profit adds to closing.
    """
    pnl = generate_profit_and_loss(financial_year)
    return {
        "statement": "retained_earnings_rollforward",
        "financial_year": financial_year,
        "opening_retained_earnings": "carried_forward",
        "net_profit_for_year": pnl["net_profit"],
        "closing_retained_earnings": "opening + net_profit",
        "gaap_note": "Net profit is closed to equity at year-end."
    }
