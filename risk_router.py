"""
Task 9.2 — Risk Router (DRY-RUN ONLY)

Purpose:
- Consume hypothetical signals
- Evaluate risk & position sizing
- Record allow/block decisions
- NO execution
- NO broker interaction
- Safe for replay pipelines

This module is intentionally stateless and side-effect free.
"""

from dataclasses import dataclass
from typing import Dict, Optional
from risk_positioning import RiskConfig, compute_position_size


@dataclass
class RiskDecision:
    allowed: bool
    lot_size: float
    risk_amount: float
    reason: str


@dataclass
class RiskRouterCounters:
    decisions_total: int = 0
    allowed: int = 0
    blocked: int = 0


class RiskRouter:
    """
    Risk decision engine.
    """

    def __init__(self, risk_cfg: RiskConfig):
        self.risk_cfg = risk_cfg
        self.counters = RiskRouterCounters()

    def evaluate_signal(self, signal_present: bool) -> Optional[RiskDecision]:
        """
        Evaluate a hypothetical signal.

        If no signal exists, returns None and does not increment counters.
        """

        if not signal_present:
            return None

        self.counters.decisions_total += 1

        result = compute_position_size(self.risk_cfg)

        if not result.valid or result.lot_size <= 0:
            self.counters.blocked += 1
            return RiskDecision(
                allowed=False,
                lot_size=0.0,
                risk_amount=0.0,
                reason=result.reason,
            )

        self.counters.allowed += 1
        return RiskDecision(
            allowed=True,
            lot_size=result.lot_size,
            risk_amount=result.risk_amount,
            reason="risk_ok",
        )

    def snapshot(self) -> Dict[str, int]:
        """
        Lightweight counters snapshot.
        """
        return {
            "risk_decisions_total": self.counters.decisions_total,
            "risk_allowed": self.counters.allowed,
            "risk_blocked": self.counters.blocked,
        }


# --- self-test (safe, optional) ---
if __name__ == "__main__":
    cfg = RiskConfig(
        account_equity=10_000,
        risk_per_trade=0.01,
        stop_loss_pips=20,
        pip_value_per_lot=10,
    )

    router = RiskRouter(cfg)

    # simulate signals
    for flag in [False, True, True, False, True]:
        decision = router.evaluate_signal(flag)
        if decision:
            print(decision)

    print("=== RISK ROUTER COUNTERS ===")
    print(router.snapshot())