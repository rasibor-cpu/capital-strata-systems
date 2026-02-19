"""
Weekly Rebalance Engine
Capital Strata Systems / REA

Hybrid Model:
- Calendar based (Friday 17:00 ET)
- Drift threshold required
- Fail-closed
- No mid-session capital mutation
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict


@dataclass
class RebalanceResult:
    should_rebalance: bool
    reason: str
    drift_snapshot: Dict[str, float]


class WeeklyRebalanceEngine:
    def __init__(
        self,
        target_weights: Dict[str, float],
        drift_threshold: float = 0.05  # 5% drift default
    ):
        self.target_weights = target_weights
        self.drift_threshold = drift_threshold

    # -------------------------
    # Time Logic
    # -------------------------

    def _is_rebalance_time(self, now: datetime) -> bool:
        # Friday = 4 (Monday=0)
        return now.weekday() == 4 and now.hour >= 17

    # -------------------------
    # Drift Logic
    # -------------------------

    def _calculate_drift(
        self,
        current_allocations: Dict[str, float]
    ) -> Dict[str, float]:

        drift = {}

        total = sum(current_allocations.values())
        if total <= 0:
            return drift

        for instrument, current_value in current_allocations.items():
            current_weight = current_value / total
            target_weight = self.target_weights.get(instrument, 0.0)

            drift[instrument] = current_weight - target_weight

        return drift

    def _drift_exceeds_threshold(self, drift: Dict[str, float]) -> bool:
        for v in drift.values():
            if abs(v) >= self.drift_threshold:
                return True
        return False

    # -------------------------
    # Public Interface
    # -------------------------

    def evaluate(
        self,
        now: datetime,
        current_allocations: Dict[str, float]
    ) -> RebalanceResult:

        try:
            if not self._is_rebalance_time(now):
                return RebalanceResult(
                    False,
                    "Not rebalance window",
                    {}
                )

            drift = self._calculate_drift(current_allocations)

            if not drift:
                return RebalanceResult(
                    False,
                    "Invalid allocation snapshot",
                    {}
                )

            if not self._drift_exceeds_threshold(drift):
                return RebalanceResult(
                    False,
                    "Drift below threshold",
                    drift
                )

            return RebalanceResult(
                True,
                "Drift threshold exceeded — rebalance approved",
                drift
            )

        except Exception as e:
            return RebalanceResult(
                False,
                f"Exception: {str(e)}",
                {}
            )
