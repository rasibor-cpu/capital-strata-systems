"""
Capital Strata Systems (CSS)
Phase 26D-6 – Balance Sheet Engine (Institutional, Contra-Accurate, Customer-Aware)

Rules:
- Normal ASSET: value = DR - CR, contributes +value to Total Assets
- Contra ASSET (group contains 'CONTRA'): contra = CR - DR, contributes -contra to Total Assets
- LIABILITY: value = CR - DR
- EQUITY: value = CR - DR

Customer handling (BANK model):
- Customer accounts are liabilities (customer deposits).
- We only include canonical customer accounts that start with 'CUST-840-'.
  This prevents legacy/test IDs like 'CUST-0001' from polluting the balance sheet.

Period handling:
- If period is 'YYYY-MM' => includes journal entries with execution_date <= last day of that month
- If period is 'YYYY-MM-DD' => includes journal entries with execution_date <= that day
"""

from __future__ import annotations

from decimal import Decimal
from collections import defaultdict
from pathlib import Path
from datetime import datetime, date
import calendar
import json


JOURNAL_FILE = Path("audit_logs/journal.jsonl")
COA_FILE = Path("backend/app/config/chart_of_accounts.json")

CUSTOMER_PREFIX = "CUST-840-"  # canonical customer liability account format


def _to_decimal(x) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal("0")


def _parse_date_ymd(s: str) -> date | None:
    s = (s or "").strip()
    if len(s) < 10:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _period_cutoff(period: str) -> date | None:
    """
    period: 'YYYY-MM' or 'YYYY-MM-DD'
    """
    p = (period or "").strip()
    if not p:
        return None

    # YYYY-MM-DD
    if len(p) >= 10 and p[4] == "-" and p[7] == "-":
        return _parse_date_ymd(p)

    # YYYY-MM
    if len(p) >= 7 and p[4] == "-":
        try:
            y = int(p[:4])
            m = int(p[5:7])
            last_day = calendar.monthrange(y, m)[1]
            return date(y, m, last_day)
        except Exception:
            return None

    return None


def _load_coa() -> dict:
    data = json.loads(COA_FILE.read_text(encoding="utf-8"))
    coa = {}
    for a in data.get("accounts", []):
        if not isinstance(a, dict):
            continue
        acc = str(a.get("account_no", "")).strip()
        if acc:
            coa[acc] = a
    return coa


def _load_balances(period: str) -> dict:
    """
    Reads journal.jsonl and accumulates DR/CR by account_no up to period cutoff.
    Skips blank lines and malformed JSON safely.
    """
    balances = defaultdict(lambda: {"DR": Decimal("0"), "CR": Decimal("0")})

    if not JOURNAL_FILE.exists():
        return balances

    cutoff = _period_cutoff(period)

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for raw in f:
            line = (raw or "").strip()
            if not line:
                continue

            try:
                j = json.loads(line)
            except Exception:
                continue

            acc = str(j.get("account_no", "")).strip()
            side = str(j.get("side", "")).upper().strip()
            amt = _to_decimal(j.get("amount", "0"))

            if not acc or side not in {"DR", "CR"}:
                continue

            if cutoff is not None:
                exec_date = _parse_date_ymd(str(j.get("execution_date", "")).strip())
                if exec_date is None:
                    continue
                if exec_date > cutoff:
                    continue

            balances[acc][side] += amt

    return balances


def generate_balance_sheet(period: str) -> dict:
    coa = _load_coa()
    balances = _load_balances(period)

    assets: dict[str, Decimal] = {}
    contra_assets: dict[str, Decimal] = {}
    liabilities: dict[str, Decimal] = {}
    equity: dict[str, Decimal] = {}

    total_assets = Decimal("0")
    total_contra = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity = Decimal("0")

    # 1) COA-driven accounts
    for acc_no, meta in coa.items():
        acc_type = str(meta.get("type", "")).upper().strip()
        group = str(meta.get("group", "")).upper().strip()

        dr = balances[acc_no]["DR"]
        cr = balances[acc_no]["CR"]

        if acc_type == "ASSET":
            if "CONTRA" in group:
                contra = cr - dr
                if contra != 0:
                    contra_assets[acc_no] = contra
                    total_contra += contra
            else:
                value = dr - cr
                if value != 0:
                    assets[acc_no] = value
                    total_assets += value

        elif acc_type == "LIABILITY":
            value = cr - dr
            if value != 0:
                liabilities[acc_no] = value
                total_liabilities += value

        elif acc_type == "EQUITY":
            value = cr - dr
            if value != 0:
                equity[acc_no] = value
                total_equity += value

    # 2) Canonical customer accounts (dynamic liabilities)
    for acc_no, sides in balances.items():
        if acc_no in coa:
            continue

        # Only include canonical customer IDs
        if not acc_no.upper().startswith(CUSTOMER_PREFIX):
            continue

        dr = sides["DR"]
        cr = sides["CR"]
        value = cr - dr  # liability normal credit

        if value != 0:
            liabilities[acc_no] = value
            total_liabilities += value

    net_assets = total_assets - total_contra

    return {
        "period": period,
        "assets": assets,
        "contra_assets": contra_assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets_gross": total_assets,
        "total_contra_assets": total_contra,
        "total_assets_net": net_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "balanced": net_assets == (total_liabilities + total_equity),
    }


def print_balance_sheet(period: str) -> None:
    bs = generate_balance_sheet(period)

    def fmt(x: Decimal) -> str:
        return f"{x:,.2f}"

    print("\n" + "=" * 60)
    print("CAPITAL STRATA SYSTEMS (CSS)")
    print("BALANCE SHEET")
    print(f"As at: {period}")
    print("=" * 60)

    print("\nASSETS (GROSS)")
    print("-" * 60)
    for acc in sorted(bs["assets"].keys()):
        print(f"{acc:<20} {fmt(bs['assets'][acc]):>15}")
    print(f"{'Total Assets (Gross)':<20} {fmt(bs['total_assets_gross']):>15}")

    print("\nLESS: CONTRA ASSETS")
    print("-" * 60)
    for acc in sorted(bs["contra_assets"].keys()):
        print(f"{acc:<20} {fmt(bs['contra_assets'][acc]):>15}")
    print(f"{'Total Contra Assets':<20} {fmt(bs['total_contra_assets']):>15}")

    print("\nTOTAL ASSETS (NET)")
    print("-" * 60)
    print(f"{'Total Assets (Net)':<20} {fmt(bs['total_assets_net']):>15}")

    print("\nLIABILITIES")
    print("-" * 60)
    for acc in sorted(bs["liabilities"].keys()):
        print(f"{acc:<20} {fmt(bs['liabilities'][acc]):>15}")
    print(f"{'Total Liabilities':<20} {fmt(bs['total_liabilities']):>15}")

    print("\nEQUITY")
    print("-" * 60)
    for acc in sorted(bs["equity"].keys()):
        print(f"{acc:<20} {fmt(bs['equity'][acc]):>15}")
    print(f"{'Total Equity':<20} {fmt(bs['total_equity']):>15}")

    print("\n" + "=" * 60)
    print("Assets (Net) = Liabilities + Equity ?", bs["balanced"])
    print("=" * 60 + "\n")