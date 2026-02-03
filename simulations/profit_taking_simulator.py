"""
REA Capital — Governance Profit-Taking Simulator
SAFE / READ-ONLY / NO EXECUTION

Purpose:
- Prove governance-locked profit-taking rules
- Simulate tiered cash-out + capped re-entry
- Deterministic, auditable output

Canonical governance source:
- governance/profit_taking_policy.py (get_policy_snapshot)
"""

from __future__ import annotations
from typing import List
from dataclasses import dataclass

from governance.profit_taking_policy import get_policy_snapshot


@dataclass
class ProfitEvent:
    step: int
    unrealized_pnl: float
    realized_pnl: float
    active_capital: float
    note: str


def simulate_profit_lifecycle(
    starting_capital: float,
    pnl_path: List[float],
) -> List[ProfitEvent]:
    """
    pnl_path = cumulative PnL as a fraction of starting capital
    Example: 0.12 means +12%
    """

    policy = get_policy_snapshot()

    tiers = sorted(policy["profit_tiers"])
    max_reentry_frac = policy["max_reentry_fraction_of_realized_profit"]

    realized = 0.0
    active_capital = starting_capital
    last_tier = 0.0

    events: List[ProfitEvent] = []

    for i, pnl_frac in enumerate(pnl_path, start=1):
        unrealized = active_capital * pnl_frac
        note = "NO_ACTION"

        hit_tiers = [t for t in tiers if last_tier < t <= pnl_frac]

        if hit_tiers:
            highest = max(hit_tiers)
            cashout_fraction = highest - last_tier
            cashout_amount = starting_capital * cashout_fraction

            realized += cashout_amount
            last_tier = highest

            reentry_cap = realized * max_reentry_frac
            active_capital = starting_capital + reentry_cap

            note = (
                f"HIT {highest*100:.0f}% | "
                f"CASHOUT={cashout_amount:,.2f} | "
                f"REALIZED={realized:,.2f} | "
                f"REENTRY_CAP={reentry_cap:,.2f}"
            )

        events.append(
            ProfitEvent(
                step=i,
                unrealized_pnl=unrealized,
                realized_pnl=realized,
                active_capital=active_capital,
                note=note,
            )
        )

    return events


if __name__ == "__main__":
    print("\n=== REA GOVERNANCE PROFIT-TAKING SIMULATION ===\n")

    policy = get_policy_snapshot()

    print("LOCKED POLICY (CANONICAL):")
    for k, v in policy.items():
        print(f"  {k}: {v}")

    starting_capital = 100_000.0

    pnl_path = [
        0.05,
        0.12,   # 10% tier
        0.18,
        0.22,   # 20% tier
        0.31,
        0.36,   # 35% tier
        0.48,
        0.51,   # 50% tier
    ]

    events = simulate_profit_lifecycle(starting_capital, pnl_path)

    print("\n--- SIMULATION OUTPUT ---\n")

    for e in events:
        print(
            f"Step {e.step:02d} | "
            f"Unrealized={e.unrealized_pnl:,.2f} | "
            f"Realized={e.realized_pnl:,.2f} | "
            f"ActiveCapital={e.active_capital:,.2f} | "
            f"{e.note}"
        )

    print("\n=== END SIMULATION ===")
