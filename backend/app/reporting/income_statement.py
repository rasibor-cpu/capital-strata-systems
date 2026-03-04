"""
Capital Strata Systems (CSS)
Phase 26B – Institutional Income Statement (Printable)

Enhancements:
- Account names included
- Sorted presentation
- Structured printable layout
- JSON + formatted text output
"""

from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
from typing import Dict, Any, Tuple


JOURNAL_FILE = Path("audit_logs/journal.jsonl")
COA_FILE = Path("backend/app/config/chart_of_accounts.json")


def _to_decimal(x) -> Decimal:
    return Decimal(str(x))


def _load_coa() -> Dict[str, Dict[str, Any]]:
    if not COA_FILE.exists():
        raise FileNotFoundError("chart_of_accounts.json missing")

    raw = json.loads(COA_FILE.read_text(encoding="utf-8"))
    accounts = raw.get("accounts", [])

    return {str(a["account_no"]): a for a in accounts}


def _load_journal_lines():
    if not JOURNAL_FILE.exists():
        return []

    lines = []
    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines.append(json.loads(line))
    return lines


def _period_match(execution_date: str, period: str) -> bool:
    return execution_date.startswith(period)


def _format_money(x: Decimal) -> str:
    return f"{x:,.2f}"


def generate_income_statement(period: str) -> Dict[str, Any]:
    coa = _load_coa()
    journal = _load_journal_lines()

    income_totals = defaultdict(Decimal)
    expense_totals = defaultdict(Decimal)

    for line in journal:
        exec_date = line.get("execution_date")
        if not exec_date or not _period_match(exec_date, period):
            continue

        account_no = str(line.get("account_no"))
        side = str(line.get("side")).upper()
        amount = _to_decimal(line.get("amount"))

        meta = coa.get(account_no)
        if not meta:
            continue

        acc_type = meta.get("type")

        if acc_type == "INCOME":
            if side == "CR":
                income_totals[account_no] += amount
            elif side == "DR":
                income_totals[account_no] -= amount

        elif acc_type == "EXPENSE":
            if side == "DR":
                expense_totals[account_no] += amount
            elif side == "CR":
                expense_totals[account_no] -= amount

    total_income = sum(income_totals.values(), Decimal("0"))
    total_expense = sum(expense_totals.values(), Decimal("0"))
    net_profit = total_income - total_expense

    # Sort accounts numerically
    sorted_income = sorted(income_totals.items())
    sorted_expense = sorted(expense_totals.items())

    return {
        "period": period,
        "income_accounts": [
            {
                "account_no": acc,
                "account_name": coa[acc]["name"],
                "amount": str(val),
            }
            for acc, val in sorted_income
        ],
        "expense_accounts": [
            {
                "account_no": acc,
                "account_name": coa[acc]["name"],
                "amount": str(val),
            }
            for acc, val in sorted_expense
        ],
        "total_income": str(total_income),
        "total_expense": str(total_expense),
        "net_profit": str(net_profit),
    }


def print_income_statement(period: str) -> None:
    data = generate_income_statement(period)

    print("\n")
    print("==============================================")
    print("        CAPITAL STRATA SYSTEMS (CSS)")
    print("              INCOME STATEMENT")
    print(f"               Period: {period}")
    print("==============================================\n")

    print("INCOME")
    print("----------------------------------------------")

    total_income = Decimal(data["total_income"])
    for row in data["income_accounts"]:
        amt = _to_decimal(row["amount"])
        print(f"{row['account_no']}  {row['account_name']:<35} {_format_money(amt):>15}")

    print("----------------------------------------------")
    print(f"{'Total Income':<45}{_format_money(total_income):>15}\n")

    print("EXPENSES")
    print("----------------------------------------------")

    total_expense = Decimal(data["total_expense"])
    for row in data["expense_accounts"]:
        amt = _to_decimal(row["amount"])
        print(f"{row['account_no']}  {row['account_name']:<35} {_format_money(amt):>15}")

    print("----------------------------------------------")
    print(f"{'Total Expenses':<45}{_format_money(total_expense):>15}\n")

    net_profit = Decimal(data["net_profit"])
    print("==============================================")
    print(f"{'NET PROFIT / (LOSS)':<45}{_format_money(net_profit):>15}")
    print("==============================================\n")