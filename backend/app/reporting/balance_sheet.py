"""
Capital Strata Systems (CSS)
Phase 27B – Suspense Control Integrated Balance Sheet
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from collections import defaultdict


JOURNAL_FILE = Path("audit_logs/journal.jsonl")

SUSPENSE_ACCOUNT = "000-840-999"


def _dr_cr(side: str, amount: Decimal) -> Decimal:
    if side == "DR":
        return amount
    return -amount


def generate_balance_sheet(period: str) -> dict:
    assets = defaultdict(Decimal)
    contra_assets = defaultdict(Decimal)
    liabilities = defaultdict(Decimal)
    equity = defaultdict(Decimal)

    for line in JOURNAL_FILE.open():
        if not line.strip():
            continue

        j = json.loads(line)

        if not j.get("transaction_date", "").startswith(period):
            continue

        account = j["account_no"]
        amount = Decimal(j["amount"])
        value = _dr_cr(j["side"], amount)

        # ------------------------------
        # Classification Rules
        # ------------------------------

        if account.startswith("000-840-0") or account.startswith("000-840-8"):
            assets[account] += value

        elif account.startswith("000-840-3050"):
            contra_assets[account] += value

        elif account.startswith("000-840-3") or account.startswith("CUST-840-"):
            liabilities[account] += (-value)

        elif account.startswith("000-840-5"):
            equity[account] += (-value)

    total_assets_gross = sum(assets.values())
    total_contra = sum(contra_assets.values())
    total_assets_net = total_assets_gross - total_contra
    total_liabilities = sum(liabilities.values())
    total_equity = sum(equity.values())

    suspense_balance = assets.get(SUSPENSE_ACCOUNT, Decimal("0"))

    return {
        "assets": dict(assets),
        "contra": dict(contra_assets),
        "liabilities": dict(liabilities),
        "equity": dict(equity),
        "total_assets_net": total_assets_net,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "balanced": total_assets_net == (total_liabilities + total_equity),
        "suspense_balance": suspense_balance
    }


def print_balance_sheet(period: str):
    bs = generate_balance_sheet(period)

    print("=" * 70)
    print("CAPITAL STRATA SYSTEMS (CSS)")
    print("BALANCE SHEET")
    print(f"As at: {period}")
    print("=" * 70)

    print("\nASSETS (GROSS)")
    print("-" * 70)
    for k, v in bs["assets"].items():
        print(f"{k:<20} {v:>15,.2f}")

    print("\nLESS: CONTRA ASSETS")
    print("-" * 70)
    for k, v in bs["contra"].items():
        print(f"{k:<20} {v:>15,.2f}")

    print("\nLIABILITIES")
    print("-" * 70)
    for k, v in bs["liabilities"].items():
        print(f"{k:<20} {v:>15,.2f}")

    print("\nEQUITY")
    print("-" * 70)
    for k, v in bs["equity"].items():
        print(f"{k:<20} {v:>15,.2f}")

    print("\n" + "=" * 70)
    print(f"Assets (Net) = {bs['total_assets_net']:,.2f}")
    print(f"Liabilities + Equity = {(bs['total_liabilities'] + bs['total_equity']):,.2f}")
    print(f"Balanced ? {bs['balanced']}")
    print("=" * 70)

    # Suspense Warning
    if bs["suspense_balance"] != Decimal("0"):
        print("\n*** WARNING: Suspense Account Not Cleared ***")
        print(f"SUSPENSE BALANCE: {bs['suspense_balance']:,.2f}")
        print("System Integrity Compromised Until Resolved.")