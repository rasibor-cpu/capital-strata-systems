"""
Weekly Rebalance Engine – Dynamic Drift (Volatility + Regime aware)
Capital Strata Systems

Hybrid enforcement:
- Calendar window: Friday 17:00 ET onward
- Only triggers if allocation drift exceeds dynamic threshold
- Used as a BLOCK gate for new trades (no mid-session capital mutation)
- Fail-closed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None


@dataclass
class RebalanceResult:
    should_rebalance: bool
    reason: str
    drift_snapshot: Dict[str, float]
    effective_threshold: float


class WeeklyRebalanceEngine:
    def __init__(self, target_weights: Dict[str, float], base_threshold: float = 0.05):
        self.target_weights = target_weights or {}
        self.base_threshold = float(base_threshold)

    # -------------------------
    # time gate (Friday 17:00 ET)
    # -------------------------
    def _is_rebalance_time(self, now_utc: datetime) -> bool:
        if ZoneInfo is None:
            # fallback: UTC only (safe + explicit)
            # Friday=4; 17:00 UTC is NOT the same as ET, but we fail gracefully
            return now_utc.weekday() == 4 and now_utc.hour >= 17

        et = ZoneInfo("America/New_York")
        now_et = now_utc.astimezone(et)

        # Friday = 4
        return now_et.weekday() == 4 and now_et.hour >= 17

    # -------------------------
    # dynamic threshold
    # -------------------------
    def _compute_dynamic_threshold(self, volatility_state: str, regime_state: str) -> float:
        vol = (volatility_state or "MEDIUM").upper()
        reg = (regime_state or "NORMAL").upper()

        volatility_map = {"HIGH": 0.6, "MEDIUM": 1.0, "LOW": 1.3}
        regime_map = {"DEFENSIVE": 0.75, "NORMAL": 1.0, "AGGRESSIVE": 1.2}

        vol_factor = volatility_map.get(vol, 1.0)
        reg_factor = regime_map.get(reg, 1.0)

        return self.base_threshold * vol_factor * reg_factor

    # -------------------------
    # drift
    # -------------------------
    def _calculate_drift(self, current_allocations: Dict[str, float]) -> Dict[str, float]:
        current_allocations = current_allocations or {}
        total = sum(float(v) for v in current_allocations.values()) if current_allocations else 0.0
        if total <= 0:
            return {}

        drift: Dict[str, float] = {}
        for instr, value in current_allocations.items():
            cur_w = float(value) / total
            tgt_w = float(self.target_weights.get(instr, 0.0))
            drift[instr] = cur_w - tgt_w
        return drift

    # -------------------------
    # public
    # -------------------------
    def evaluate(
        self,
        *,
        now_utc: datetime,
        current_allocations: Dict[str, float],
        volatility_state: str,
        regime_state: str,
    ) -> RebalanceResult:
        try:
            if not self.target_weights:
                return RebalanceResult(
                    False,
                    "No target weights configured (rebalance skipped)",
                    {},
                    0.0,
                )

            if not self._is_rebalance_time(now_utc):
                return RebalanceResult(False, "Not rebalance window", {}, 0.0)

            drift = self._calculate_drift(current_allocations)
            if not drift:
                return RebalanceResult(False, "Invalid/empty allocations snapshot", {}, 0.0)

            thr = self._compute_dynamic_threshold(volatility_state, regime_state)

            for v in drift.values():
                if abs(v) >= thr:
                    return RebalanceResult(True, "Dynamic drift threshold exceeded", drift, thr)

            return RebalanceResult(False, "Drift within dynamic tolerance", drift, thr)

        except Exception as e:
            return RebalanceResult(False, f"Exception: {str(e)}", {}, 0.0)
