"""
Capital Strata Systems (CSS)
Phase 25B – Financial Statement Engine (Enhanced)

Generates:
- Trial Balance
- Income Statement
- Balance Sheet
- Statement of Changes in Equity
- Statement of Use of Funds / Cash Flow (Operating vs Investing vs Financing)

Core assumptions for Use of Funds:
- Cash/bank accounts are identified by COA group in {"CASH","NOSTRO"}.
- We group journal legs by transaction_id within the period.
- For each transaction, we compute net cash movement (sum of cash legs).
- We classify that cash movement based on the dominant non-cash leg types:
    * INCOME/EXPENSE -> OPERATING
    * ASSET (non-cash) -> INVESTING
    * LIABILITY/EQUITY -> FINANCING
"""

from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal
from typing import Dict, Any, List, Tuple


JOURNAL_FILE = Path("audit_logs/journal.jsonl")
COA_FILE = Path("backend/app/config/chart_of_accounts.json")


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def _to_decimal(v) -> Decimal:
    return Decimal(str(v))


def _load_coa() -> Dict[str, Any]:
    with COA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    coa_index: Dict[str, Any] = {}
    for acc in data.get("accounts", []):
        coa_index[str(acc["account_no"])] = acc
    return coa_index


def _filter_period(entry: Dict[str, Any], period: str) -> bool:
    # period format: YYYY-MM
    return str(entry.get("execution_date", "")).startswith(period)


def _iter_journal_period(period: str):
    if not JOURNAL_FILE.exists():
        return
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            j = json.loads(line)
            if _filter_period(j, period):
                yield j


def _is_cash_account(coa_meta: Dict[str, Any]) -> bool:
    return str(coa_meta.get("group", "")).upper() in {"CASH", "NOSTRO"}


def _signed_amount_from_leg(side: str, amount: Decimal) -> Decimal:
    # Journal convention: DR increases the account balance; CR decreases it
    s = str(side).upper()
    if s == "DR":
        return amount
    if s == "CR":
        return -amount
    raise ValueError(f"Invalid side: {side}")


def _compute_account_balances(period: str) -> Dict[str, Decimal]:
    balances: Dict[str, Decimal] = {}
    for j in _iter_journal_period(period):
        acc = str(j["account_no"])
        amt = _to_decimal(j["amount"])
        balances.setdefault(acc, Decimal("0"))
        balances[acc] += _signed_amount_from_leg(j["side"], amt)
    return balances


# ---------------------------------------------------
# 1. Trial Balance
# ---------------------------------------------------

def generate_trial_balance(period: str) -> Dict[str, Any]:
    coa = _load_coa()
    balances = _compute_account_balances(period)

    trial: List[Dict[str, Any]] = []
    total_dr = Decimal("0")
    total_cr = Decimal("0")

    for acc_no, bal in sorted(balances.items()):
        meta = coa.get(acc_no)
        if not meta:
            # Unknown account ignored (should not happen if governance is correct)
            continue

        normal = str(meta.get("normal_balance", "")).upper()

        # Convert signed balance into TB DR/CR presentation using normal balance
        if normal == "DEBIT":
            dr = bal if bal > 0 else Decimal("0")
            cr = -bal if bal < 0 else Decimal("0")
        else:
            cr = bal if bal > 0 else Decimal("0")
            dr = -bal if bal < 0 else Decimal("0")

        total_dr += dr
        total_cr += cr

        trial.append({
            "account_no": acc_no,
            "account_name": meta.get("name", ""),
            "type": meta.get("type", ""),
            "group": meta.get("group", ""),
            "report_group": meta.get("report_group", ""),
            "debit": str(dr),
            "credit": str(cr),
        })

    return {
        "period": period,
        "trial_balance": trial,
        "total_debits": str(total_dr),
        "total_credits": str(total_cr),
        "balanced": (total_dr == total_cr),
    }


# ---------------------------------------------------
# 2. Income Statement
# ---------------------------------------------------

def generate_income_statement(period: str) -> Dict[str, Any]:
    coa = _load_coa()
    balances = _compute_account_balances(period)

    income_total = Decimal("0")
    expense_total = Decimal("0")
    lines: List[Dict[str, Any]] = []

    for acc_no, bal in balances.items():
        meta = coa.get(acc_no)
        if not meta:
            continue

        t = str(meta.get("type", "")).upper()

        # For INCOME and EXPENSE, we want positive presentation amounts.
        # Balances here are "signed" per journal convention; presentation should be absolute.
        if t == "INCOME":
            amt = abs(bal)
            income_total += amt
            lines.append({"account_no": acc_no, "account": meta.get("name", ""), "amount": str(amt)})

        elif t == "EXPENSE":
            amt = abs(bal)
            expense_total += amt
            lines.append({"account_no": acc_no, "account": meta.get("name", ""), "amount": str(amt)})

    net_profit = income_total - expense_total

    return {
        "period": period,
        "income_total": str(income_total),
        "expense_total": str(expense_total),
        "net_profit": str(net_profit),
        "lines": lines,
    }


# ---------------------------------------------------
# 3. Balance Sheet (simple aggregation by type)
# ---------------------------------------------------

def generate_balance_sheet(period: str) -> Dict[str, Any]:
    coa = _load_coa()
    balances = _compute_account_balances(period)

    assets = Decimal("0")
    liabilities = Decimal("0")
    equity = Decimal("0")

    for acc_no, bal in balances.items():
        meta = coa.get(acc_no)
        if not meta:
            continue

        t = str(meta.get("type", "")).upper()
        is_contra = bool(meta.get("is_contra", False))

        if t == "ASSET":
            # Contra assets reduce assets; but our balances are already signed.
            # We treat by adding the signed value directly.
            assets += bal

        elif t == "LIABILITY":
            liabilities += bal

        elif t == "EQUITY":
            equity += bal

    # For presentation, liabilities/equity usually shown positive.
    return {
        "period": period,
        "assets": str(assets),
        "liabilities": str(abs(liabilities)),
        "equity": str(abs(equity)),
        "check_assets_minus_liab_equity": str(assets - (abs(liabilities) + abs(equity))),
    }


# ---------------------------------------------------
# 4. Statement of Changes in Equity (initial)
# ---------------------------------------------------

def generate_equity_statement(period: str) -> Dict[str, Any]:
    income_stmt = generate_income_statement(period)
    net_profit = Decimal(income_stmt["net_profit"])
    return {
        "period": period,
        "net_profit_added_to_retained_earnings": str(net_profit),
        "note": "Initial version assumes net profit flows into retained earnings; dividends/other movements to be added later.",
    }


# ---------------------------------------------------
# 5. Statement of Use of Funds / Cash Flow (Operating vs Investing vs Financing)
# ---------------------------------------------------

def generate_use_of_funds(period: str) -> Dict[str, Any]:
    coa = _load_coa()

    # Group legs by transaction_id within period
    tx_map: Dict[str, List[Dict[str, Any]]] = {}

    for j in _iter_journal_period(period):
        tx_id = str(j.get("transaction_id", "")).strip() or "UNKNOWN_TX"
        tx_map.setdefault(tx_id, []).append(j)

    operating_total = Decimal("0")
    investing_total = Decimal("0")
    financing_total = Decimal("0")

    operating_lines: List[Dict[str, Any]] = []
    investing_lines: List[Dict[str, Any]] = []
    financing_lines: List[Dict[str, Any]] = []

    for tx_id, legs in tx_map.items():

        # 1) Compute net cash movement for this transaction
        net_cash = Decimal("0")
        cash_legs: List[Dict[str, Any]] = []
        non_cash_legs: List[Dict[str, Any]] = []

        for leg in legs:
            acc = str(leg["account_no"])
            meta = coa.get(acc)
            if not meta:
                continue

            amt = _to_decimal(leg["amount"])
            signed = _signed_amount_from_leg(leg["side"], amt)

            if _is_cash_account(meta):
                net_cash += signed
                cash_legs.append(leg)
            else:
                non_cash_legs.append(leg)

        # If no cash movement, not a use-of-funds cashflow item
        if net_cash == 0:
            continue

        # 2) Classify transaction by dominant non-cash leg type (largest absolute signed amount)
        # If we cannot determine, default to OPERATING (conservative reporting).
        dominant_type = "OPERATING"
        dominant_abs = Decimal("0")
        dominant_name = ""

        for leg in non_cash_legs:
            acc = str(leg["account_no"])
            meta = coa.get(acc)
            if not meta:
                continue
            amt = _to_decimal(leg["amount"])
            signed = _signed_amount_from_leg(leg["side"], amt)
            a = abs(signed)
            if a > dominant_abs:
                dominant_abs = a
                t = str(meta.get("type", "")).upper()
                rg = str(meta.get("report_group", "")).upper()

                # Classification rules:
                if t in {"INCOME", "EXPENSE"}:
                    dominant_type = "OPERATING"
                elif t == "ASSET":
                    # Non-cash assets are investing (PPE, investments, etc.)
                    dominant_type = "INVESTING"
                elif t in {"LIABILITY", "EQUITY"}:
                    dominant_type = "FINANCING"
                else:
                    dominant_type = "OPERATING"

                dominant_name = meta.get("name", "")

        # 3) Present as cash inflow/outflow lines
        # Convention: positive net_cash = increase in cash (inflow), negative = outflow
        line = {
            "transaction_id": tx_id,
            "cash_change": str(net_cash),
            "classification_driver": dominant_name or "Unclassified (default operating)",
            "ticket_id": str(legs[0].get("ticket_id", "")),
            "execution_date": str(legs[0].get("execution_date", "")),
            "description": str(legs[0].get("description", "")),
        }

        if dominant_type == "OPERATING":
            operating_total += net_cash
            operating_lines.append(line)
        elif dominant_type == "INVESTING":
            investing_total += net_cash
            investing_lines.append(line)
        else:
            financing_total += net_cash
            financing_lines.append(line)

    net_change_in_cash = operating_total + investing_total + financing_total

    return {
        "period": period,
        "operating_net": str(operating_total),
        "investing_net": str(investing_total),
        "financing_net": str(financing_total),
        "net_change_in_cash": str(net_change_in_cash),
        "operating_lines": operating_lines,
        "investing_lines": investing_lines,
        "financing_lines": financing_lines,
        "note": "Classification is transaction-based using dominant non-cash leg type. This is suitable for statement-of-use-of-funds reporting and can be refined with instrument-level rules later.",
    }