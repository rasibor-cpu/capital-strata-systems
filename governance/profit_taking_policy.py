"""
REA Capital Trading Engine — Governance Policy
Profit-taking + re-entry risk cap policy (prompt-only safe).

Authoritative rule (as agreed):
- Take-profit tiers: 10%, 20%, 35%, 50%
- When a tier is hit: cash out / lock profits.
- Re-entry capital is capped at <= 50% of REALIZED profits already made.
- No martingale / no escalation based on unrealized P&L.
- Each re-entry begins a new trade lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ProfitTakingPolicy:
    # Tier thresholds are expressed as decimal returns: 0.10 == 10%
    profit_tiers: Tuple[float, ...] = (0.10, 0.20, 0.35, 0.50)

    # Re-entry is capped at this fraction of realized profits
    max_reentry_fraction_of_realized_profit: float = 0.50

    # Governance invariants
    principal_protection: bool = True
    lifecycle_reset_on_reentry: bool = True
    martingale_allowed: bool = False
    use_unrealized_gains_for_reentry: bool = False

    def validate(self) -> None:
        if not self.profit_tiers:
            raise ValueError("profit_tiers must not be empty")

        # strictly increasing tiers
        for i in range(1, len(self.profit_tiers)):
            if self.profit_tiers[i] <= self.profit_tiers[i - 1]:
                raise ValueError("profit_tiers must be strictly increasing")

        # reasonable bounds (0% < tier <= 500% just to avoid nonsense)
        for t in self.profit_tiers:
            if not (0.0 < t <= 5.0):
                raise ValueError(f"profit tier out of bounds: {t}")

        if not (0.0 < self.max_reentry_fraction_of_realized_profit <= 1.0):
            raise ValueError("max_reentry_fraction_of_realized_profit must be in (0, 1]")

        if self.martingale_allowed:
            raise ValueError("martingale_allowed MUST remain False by governance")

        if self.use_unrealized_gains_for_reentry:
            raise ValueError("use_unrealized_gains_for_reentry MUST remain False by governance")


def compute_reentry_cap(realized_profit_amount: float, policy: ProfitTakingPolicy) -> float:
    """
    Max allowed capital for re-entry based ONLY on realized profits.
    """
    policy.validate()
    if realized_profit_amount <= 0:
        return 0.0
    return realized_profit_amount * policy.max_reentry_fraction_of_realized_profit


def highest_profit_tier_hit(
    entry_price: float,
    current_price: float,
    policy: ProfitTakingPolicy,
) -> Optional[float]:
    """
    Returns the highest tier (e.g., 0.20) that has been reached, or None if none reached.
    Long-only return definition: (current - entry) / entry
    """
    policy.validate()
    if entry_price <= 0:
        raise ValueError("entry_price must be > 0")

    r = (current_price - entry_price) / entry_price
    hit = None
    for tier in policy.profit_tiers:
        if r >= tier:
            hit = tier
        else:
            break
    return hit


def policy_as_dict(policy: ProfitTakingPolicy) -> Dict:
    """
    Serialize policy for audit logs / prompts / UI display.
    """
    policy.validate()
    return {
        "profit_tiers": list(policy.profit_tiers),
        "max_reentry_fraction_of_realized_profit": policy.max_reentry_fraction_of_realized_profit,
        "principal_protection": policy.principal_protection,
        "lifecycle_reset_on_reentry": policy.lifecycle_reset_on_reentry,
        "martingale_allowed": policy.martingale_allowed,
        "use_unrealized_gains_for_reentry": policy.use_unrealized_gains_for_reentry,
    }


# Default authoritative policy instance
DEFAULT_PROFIT_TAKING_POLICY = ProfitTakingPolicy()
