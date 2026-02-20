"""
DrawdownScaler – Canonical Interface
Capital Strata Systems (CSS)

Purpose:
- Scale notional down as drawdown increases
- Policy-driven throttling
- Provides canonical .scale(...) method required by ExecutionGate

Fail-safe:
- Any invalid inputs => returns 0.0 notional (conservative)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class DrawdownPolicy:
    """
    A simple, policy-based mapping:
    - below soft_dd: no scaling (1.0)
    - between soft_dd and hard_dd: linear scaling down
    - above hard_dd: near-stop (floor)
    """
    soft_dd: float = 0.05       # 5%
    hard_dd: float = 0.20       # 20%
    floor: float = 0.10         # minimum 10% of notional


class DrawdownScaler:
    """
    Canonical scaler used by ExecutionGate.

    scale(notional, equity, equity_peak, policy) -> scaled_notional
    """

    def __init__(self) -> None:
        self.policies: Dict[str, DrawdownPolicy] = {
            "core": DrawdownPolicy(soft_dd=0.05, hard_dd=0.20, floor=0.10),
            "micro": DrawdownPolicy(soft_dd=0.03, hard_dd=0.12, floor=0.05),
            "defensive": DrawdownPolicy(soft_dd=0.02, hard_dd=0.08, floor=0.02),
        }

    def _get_policy(self, policy: str) -> DrawdownPolicy:
        return self.policies.get(policy, self.policies["core"])

    def _drawdown_pct(self, equity: float, equity_peak: float) -> float:
        if equity_peak <= 0:
            return 0.0
        dd = (equity_peak - equity) / equity_peak
        if dd < 0:
            return 0.0
        return float(dd)

    def scale(
        self,
        *,
        notional: float,
        equity: float,
        equity_peak: float,
        policy: str = "core",
    ) -> float:
        """
        Canonical method used by ExecutionGate.
        Returns scaled notional.
        """

        # Conservative guards
        if notional <= 0:
            return 0.0
        if equity <= 0 or equity_peak <= 0:
            return 0.0

        p = self._get_policy(policy)
        dd = self._drawdown_pct(equity=equity, equity_peak=equity_peak)

        # No scaling below soft drawdown
        if dd <= p.soft_dd:
            return float(notional)

        # Heavy scaling at/above hard drawdown
        if dd >= p.hard_dd:
            return float(notional) * float(p.floor)

        # Linear interpolation between 1.0 and floor across [soft_dd, hard_dd]
        span = (p.hard_dd - p.soft_dd)
        if span <= 0:
            return float(notional) * float(p.floor)

        t = (dd - p.soft_dd) / span  # 0..1
        scale_factor = (1.0 - t) + (p.floor * t)

        return float(notional) * float(scale_factor)

    # Backwards compatibility (if old code called .apply)
    def apply(
        self,
        *,
        notional: float,
        equity: float,
        equity_peak: float,
        policy: str = "core",
    ) -> float:
        return self.scale(
            notional=notional,
            equity=equity,
            equity_peak=equity_peak,
            policy=policy,
        )