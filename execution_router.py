"""
Task 10.1 — Execution Router (DRY-RUN, GUARDED)

Purpose:
- Consume risk-allowed decisions
- Decide whether execution WOULD occur
- NEVER place trades
- Hard-guarded by analysis_only flag

This module is architecture-only and safe by design.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ExecutionDecision:
    allowed: bool
    reason: str


@dataclass
class ExecutionCounters:
    decisions_total: int = 0
    allowed: int = 0
    blocked: int = 0


class ExecutionRouter:
    """
    Execution decision engine (dry-run only).
    """

    def __init__(self, analysis_only: bool = True):
        self.analysis_only = analysis_only
        self.counters = ExecutionCounters()

    def evaluate(self, risk_allowed: bool) -> Optional[ExecutionDecision]:
        """
        Evaluate execution eligibility from a risk decision.

        If no risk decision exists, returns None.
        """

        self.counters.decisions_total += 1

        if self.analysis_only:
            self.counters.blocked += 1
            return ExecutionDecision(
                allowed=False,
                reason="analysis_only_guard",
            )

        if not risk_allowed:
            self.counters.blocked += 1
            return ExecutionDecision(
                allowed=False,
                reason="blocked_by_risk",
            )

        self.counters.allowed += 1
        return ExecutionDecision(
            allowed=True,
            reason="execution_allowed",
        )

    def snapshot(self) -> Dict[str, int]:
        """
        Lightweight counters snapshot.
        """
        return {
            "execution_decisions_total": self.counters.decisions_total,
            "execution_allowed": self.counters.allowed,
            "execution_blocked": self.counters.blocked,
        }


# --- self-test (safe, optional) ---
if __name__ == "__main__":
    router = ExecutionRouter(analysis_only=True)

    # simulate incoming risk decisions
    for risk_flag in [True, True, False, True]:
        decision = router.evaluate(risk_flag)
        print(decision)

    print("=== EXECUTION ROUTER COUNTERS ===")
    print(router.snapshot())