from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any
import hashlib
import json


# ============================================================
# REA GOVERNANCE — PROFIT-TAKING POLICY (CANONICAL)
# ============================================================
# - SINGLE SOURCE OF TRUTH
# - STRATEGY-AGNOSTIC
# - PROMPT / SIMULATION / EXECUTION SAFE
# - NO MARTINGALE
# - NO UNREALIZED-GAINS RE-ENTRY
# ============================================================


@dataclass(frozen=True)
class ProfitTakingPolicy:
    profit_tiers: List[float]
    max_reentry_fraction_of_realized_profit: float
    principal_protection: bool
    lifecycle_reset_on_reentry: bool
    martingale_allowed: bool
    use_unrealized_gains_for_reentry: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "profit_tiers": list(self.profit_tiers),
            "max_reentry_fraction_of_realized_profit": self.max_reentry_fraction_of_realized_profit,
            "principal_protection": self.principal_protection,
            "lifecycle_reset_on_reentry": self.lifecycle_reset_on_reentry,
            "martingale_allowed": self.martingale_allowed,
            "use_unrealized_gains_for_reentry": self.use_unrealized_gains_for_reentry,
        }

    def determinism_hash(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


# ============================================================
# 🔒 LOCKED POLICY — DO NOT MODIFY
# ============================================================

DEFAULT_PROFIT_TAKING_POLICY = ProfitTakingPolicy(
    profit_tiers=[0.10, 0.20, 0.35, 0.50],
    max_reentry_fraction_of_realized_profit=0.50,
    principal_protection=True,
    lifecycle_reset_on_reentry=True,
    martingale_allowed=False,
    use_unrealized_gains_for_reentry=False,
)


# ============================================================
# PUBLIC GOVERNANCE API
# ============================================================

def get_locked_profit_taking_policy() -> ProfitTakingPolicy:
    """
    Returns the immutable governance-approved profit-taking policy.

    ⚠️ This function MUST be used by:
        - simulations
        - analytics harness
        - execution routers
        - audit & reporting layers

    Any deviation requires governance action.
    """
    return DEFAULT_PROFIT_TAKING_POLICY


def get_policy_snapshot() -> Dict[str, Any]:
    """
    Serializable snapshot for logs, audits, analytics, and prompts.
    """
    policy = get_locked_profit_taking_policy()
    snap = policy.as_dict()
    snap["determinism_hash"] = policy.determinism_hash()
    snap["governance_locked"] = True
    return snap
