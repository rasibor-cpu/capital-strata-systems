"""
Capital Strata Systems (CSS)
Phase 28B – Institutional Balance Sheet (COA + Canonical + Suspense Safe)
"""

from __future__ import annotations
from decimal import Decimal
from collections import defaultdict
from pathlib import Path
import json


JOURNAL_FILE = Path("audit_logs/journal.jsonl")
COA_FILE = Path("backend/app/config/chart_of_accounts.json")


def _to_decimal(x) -> Decimal:
    return Decimal(str(x))


def _load_coa():
    data = json.loads(COA_FILE.read_text(encoding="utf-8"))
    coa = {}
    for a in data.get("accounts", []):
        acc = str(a.get("account_no", "")).strip()
        if acc:
            coa[acc] = a
    return coa


def _load_balances():
    balances = defaultdict(lambda: {"DR": Decimal("0"), "CR": Decimal("0")})

    if not JOURNAL_FILE.exists():
        return balances

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except Exception:
                continue

            acc = str(j.get("account_no", "")).strip()
            side = str(j.get("side", "")).upper()
            amt = _to_decimal(j.get("amount", "0"))

            if side in {"DR", "CR"}:
                balances[acc][side] += amt

    return balances


def generate_balance_sheet(period: str):

    coa = _load_coa()
    balances = _load_balances()

    assets = {}
    contra_assets = {}
    liabilities = {}
    equity = {}
    suspense_accounts = {}

    total_assets = Decimal("0")
    total_contra = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity = Decimal("0")
    total_suspense = Decimal("0")

    for acc_no, meta in coa.items():

        acc_type = str(meta.get("type", "")).upper()
        group = str(meta.get("group", "")).upper()

        dr = balances[acc_no]["DR"]
        cr = balances[acc_no]["CR"]

        # ---- ASSETS ----
        if acc_type == "ASSET":

            if "CONTRA" in group:
                value = cr - dr
                if value != 0:
                    contra_assets[acc_no] = value
                    total_contra += value
            else:
                value = dr - cr
                if value != 0:
                    assets[acc_no] = value
                    total_assets += value

        # ---- LIABILITIES ----
        elif acc_type == "LIABILITY":
            value = cr - dr
            if value != 0:
                liabilities[acc_no] = value
                total_liabilities += value

        # ---- EQUITY ----
        elif acc_type == "EQUITY":
            value = cr - dr
            if value != 0:
                equity[acc_no] = value
                total_equity += value

    # ---- Dynamic Canonical Customer Liabilities Only ----
    for acc_no, bal in balances.items():
        if acc_no.startswith("CUST-840-"):
            value = bal["CR"] - bal["DR"]
            if value != 0:
                liabilities[acc_no] = value
                total_liabilities += value

    # ---- Suspense Auto-Detection ----
    for acc_no in balances:
        if acc_no.endswith("-999"):
            value = balances[acc_no]["DR"] - balances[acc_no]["CR"]
            if value != 0:
                suspense_accounts[acc_no] = value
                total_suspense += value

    net_assets = total_assets - total_contra
    balanced = net_assets == (total_liabilities + total_equity)

    return {
        "period": period,
        "assets": assets,
        "contra_assets": contra_assets,
        "liabilities": liabilities,
        "equity": equity,
        "suspense": suspense_accounts,
        "total_assets_gross": total_assets,
        "total_contra_assets": total_contra,
        "total_assets_net": net_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_suspense": total_suspense,
        "balanced": balanced,
    }


def print_balance_sheet(period: str):

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
    for acc, val in sorted(bs["assets"].items()):
        print(f"{acc:<20} {fmt(val):>15}")
    print(f"{'Total Assets (Gross)':<20} {fmt(bs['total_assets_gross']):>15}")

    print("\nLESS: CONTRA ASSETS")
    print("-" * 60)
    for acc, val in sorted(bs["contra_assets"].items()):
        print(f"{acc:<20} {fmt(val):>15}")
    print(f"{'Total Contra Assets':<20} {fmt(bs['total_contra_assets']):>15}")

    print("\nTOTAL ASSETS (NET)")
    print("-" * 60)
    print(f"{'Total Assets (Net)':<20} {fmt(bs['total_assets_net']):>15}")

    print("\nLIABILITIES")
    print("-" * 60)
    for acc, val in sorted(bs["liabilities"].items()):
        print(f"{acc:<20} {fmt(val):>15}")
    print(f"{'Total Liabilities':<20} {fmt(bs['total_liabilities']):>15}")

    print("\nEQUITY")
    print("-" * 60)
    for acc, val in sorted(bs["equity"].items()):
        print(f"{acc:<20} {fmt(val):>15}")
    print(f"{'Total Equity':<20} {fmt(bs['total_equity']):>15}")

    if bs["suspense"]:
        print("\n⚠ SUSPENSE ACCOUNTS DETECTED")
        print("-" * 60)
        for acc, val in sorted(bs["suspense"].items()):
            print(f"{acc:<20} {fmt(val):>15}")
        print(f"{'Total Suspense':<20} {fmt(bs['total_suspense']):>15}")

    print("\n" + "=" * 60)
    print("Assets (Net) =", fmt(bs["total_assets_net"]))
    print("Liabilities + Equity =", fmt(bs["total_liabilities"] + bs["total_equity"]))
    print("Balanced ?", bs["balanced"])
    print("=" * 60 + "\n")