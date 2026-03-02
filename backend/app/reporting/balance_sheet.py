"""
Capital Strata Systems (CSS)
Balance Sheet Engine – Hardened Version

Features:
- Safe journal loading (ignores blank/malformed lines)
- Canonical COA classification
- Suspense auto-detection
- Net Assets validation
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from collections import defaultdict
from typing import Dict

COA_FILE = Path("backend/app/config/chart_of_accounts.json")
JOURNAL_FILE = Path("audit_logs/journal.jsonl")


# ============================================================
# Utilities
# ============================================================

def _to_decimal(x) -> Decimal:
    return Decimal(str(x))


def _load_coa() -> Dict[str, dict]:
    if not COA_FILE.exists():
        return {}

    with COA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return {acc["account_no"]: acc for acc in data.get("accounts", [])}


def _load_balances():
    """
    Safe journal loader:
    - Skips blank lines
    - Skips malformed JSON lines
    - Never crashes reporting layer
    """

    balances = defaultdict(lambda: {"DR": Decimal("0"), "CR": Decimal("0")})

    if not JOURNAL_FILE.exists():
        return balances

    with JOURNAL_FILE.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            try:
                j = json.loads(line)
            except Exception:
                continue

            acc = str(j.get("account_no", "")).strip()
            side = str(j.get("side", "")).upper()
            amt = _to_decimal(j.get("amount", "0"))

            if not acc or side not in {"DR", "CR"}:
                continue

            balances[acc][side] += amt

    return balances


# ============================================================
# Balance Sheet Generator
# ============================================================

def generate_balance_sheet(period: str):

    coa = _load_coa()
    balances = _load_balances()

    assets = {}
    contra_assets = {}
    liabilities = {}
    equity = {}
    suspense = {}

    for acc, side_data in balances.items():

        dr = side_data["DR"]
        cr = side_data["CR"]
        net = dr - cr

        meta = coa.get(acc)
        if not meta:
            continue

        acc_type = meta["type"]
        group = meta.get("group", "")

        if acc == "000-840-999":
            suspense[acc] = abs(net)
            continue

        if acc_type == "ASSET":
            if group == "CONTRA ASSETS":
                contra_assets[acc] = abs(net)
            else:
                assets[acc] = net

        elif acc_type == "LIABILITY":
            liabilities[acc] = abs(net)

        elif acc_type == "EQUITY":
            equity[acc] = net

    total_assets_gross = sum(assets.values(), Decimal("0"))
    total_contra = sum(contra_assets.values(), Decimal("0"))
    total_assets_net = total_assets_gross - total_contra

    total_liabilities = sum(liabilities.values(), Decimal("0"))
    total_equity = sum(equity.values(), Decimal("0"))

    return {
        "assets": assets,
        "contra_assets": contra_assets,
        "liabilities": liabilities,
        "equity": equity,
        "suspense": suspense,
        "total_assets_net": total_assets_net,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "balanced": total_assets_net == (total_liabilities + total_equity),
    }


# ============================================================
# Printer
# ============================================================

def print_balance_sheet(period: str):

    data = generate_balance_sheet(period)

    print("=" * 60)
    print("CAPITAL STRATA SYSTEMS (CSS)")
    print("BALANCE SHEET")
    print(f"As at: {period}")
    print("=" * 60)

    print("\nASSETS (GROSS)")
    print("-" * 60)
    for acc, amt in data["assets"].items():
        print(f"{acc:<20} {amt:>15,.2f}")

    print("\nLESS: CONTRA ASSETS")
    print("-" * 60)
    for acc, amt in data["contra_assets"].items():
        print(f"{acc:<20} {amt:>15,.2f}")

    print("\nLIABILITIES")
    print("-" * 60)
    for acc, amt in data["liabilities"].items():
        print(f"{acc:<20} {amt:>15,.2f}")

    print("\nEQUITY")
    print("-" * 60)
    for acc, amt in data["equity"].items():
        print(f"{acc:<20} {amt:>15,.2f}")

    if data["suspense"]:
        print("\n⚠ SUSPENSE ACCOUNTS DETECTED")
        print("-" * 60)
        for acc, amt in data["suspense"].items():
            print(f"{acc:<20} {amt:>15,.2f}")

    print("\n" + "=" * 60)
    print(f"Assets (Net)      : {data['total_assets_net']:,.2f}")
    print(f"Liabilities + Eq  : {(data['total_liabilities'] + data['total_equity']):,.2f}")
    print(f"Balanced ?        : {data['balanced']}")
    print("=" * 60)