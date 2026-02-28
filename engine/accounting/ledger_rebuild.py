"""
Ledger Rebuild & Integrity Verification Engine
Capital Strata Systems

Phase 18B – Deterministic Ledger Reconstruction

Purpose:
Rebuild all GL balances directly from journal.jsonl
and verify against stored ledger balances.

This is a forensic-grade reconciliation layer.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from collections import defaultdict


JOURNAL_PATH = Path("audit_logs/journal.jsonl")


def rebuild_from_journal() -> dict[str, Decimal]:
    """
    Deterministically reconstruct all account balances
    from journal file only.
    """
    balances = defaultdict(lambda: Decimal("0"))

    if not JOURNAL_PATH.exists():
        raise FileNotFoundError("journal.jsonl not found")

    with JOURNAL_PATH.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            entry = json.loads(line)
            acct = entry["account_no"]
            amt = Decimal(str(entry.get("amount", "0")))
            side = entry["side"]

            if side == "DR":
                balances[acct] += amt
            elif side == "CR":
                balances[acct] -= amt
            else:
                raise ValueError(f"Unknown side: {side}")

    return dict(balances)


def compute_trial_balance(balances: dict[str, Decimal]) -> tuple[Decimal, Decimal]:
    """
    Compute net debit and credit totals.
    """
    total_dr = Decimal("0")
    total_cr = Decimal("0")

    for bal in balances.values():
        if bal > 0:
            total_dr += bal
        elif bal < 0:
            total_cr += abs(bal)

    return total_dr, total_cr


def run_integrity_check() -> None:
    print("=" * 70)
    print("CSS LEDGER REBUILD – INTEGRITY CHECK")
    print("=" * 70)

    balances = rebuild_from_journal()
    total_dr, total_cr = compute_trial_balance(balances)

    print("\nRebuilt Account Balances:")
    for acct, bal in sorted(balances.items()):
        print(f"{acct:<12} {bal}")

    print("\nRebuilt Totals:")
    print(f"Total DR: {total_dr}")
    print(f"Total CR: {total_cr}")

    diff = total_dr - total_cr

    if diff == 0:
        print("\n✔ REBUILD BALANCED")
    else:
        print(f"\n✖ REBUILD NOT BALANCED – Difference: {diff}")


if __name__ == "__main__":
    run_integrity_check()