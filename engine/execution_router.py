"""
Execution Router — DRY RUN ONLY
===============================

Task 8.1:
- Accepts candidate signals
- Applies final execution eligibility checks
- Logs intended actions
- NEVER places trades
- NO MT5, NO broker, NO side effects

This module exists to prove execution plumbing
without risk or live interaction.
"""

from typing import Dict, List, Any
from datetime import datetime


class ExecutionDecision:
    """
    Immutable execution decision record.
    """

    def __init__(
        self,
        ts: datetime,
        symbol: str,
        action: str,
        price: float,
        model: str,
        reason: str,
        allowed: bool,
    ):
        self.ts = ts
        self.symbol = symbol
        self.action = action
        self.price = price
        self.model = model
        self.reason = reason
        self.allowed = allowed

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "symbol": self.symbol,
            "action": self.action,
            "price": self.price,
            "model": self.model,
            "allowed": self.allowed,
            "reason": self.reason,
        }


class ExecutionRouter:
    """
    Routes candidate signals to DRY-RUN execution decisions.
    """

    def __init__(self, analysis_only: bool = True):
        self.analysis_only = analysis_only
        self.decisions: List[ExecutionDecision] = []

    def route_signal(
        self,
        symbol: str,
        signal: Dict[str, Any],
        regime_allowed: bool,
        additional_checks: Dict[str, bool] | None = None,
    ) -> ExecutionDecision:
        """
        Determines whether a signal would be executed.
        """

        ts = signal.get("ts")
        action = signal.get("type")
        price = float(signal.get("price"))
        model = signal.get("model", "unknown")

        # Default: block unless explicitly allowed
        allowed = bool(regime_allowed)
        reasons: List[str] = []

        if not regime_allowed:
            reasons.append("blocked_by_regime")

        if additional_checks:
            for check, ok in additional_checks.items():
                if not ok:
                    allowed = False
                    reasons.append(f"check_failed:{check}")

        if self.analysis_only:
            reasons.append("analysis_only_mode")

        decision = ExecutionDecision(
            ts=ts,
            symbol=symbol,
            action=action,
            price=price,
            model=model,
            allowed=allowed,
            reason=";".join(reasons) if reasons else "ok",
        )

        self.decisions.append(decision)
        return decision

    def summary(self) -> Dict[str, Any]:
        """
        Summarize dry-run execution decisions.
        """
        total = len(self.decisions)
        allowed = sum(1 for d in self.decisions if d.allowed)
        blocked = total - allowed

        return {
            "decisions_total": total,
            "decisions_allowed": allowed,
            "decisions_blocked": blocked,
            "analysis_only": self.analysis_only,
        }

    def dump(self) -> List[Dict[str, Any]]:
        """
        Return all decisions as serializable dicts.
        """
        return [d.as_dict() for d in self.decisions]