"""
EquityAuthority – Single Source of Truth
Capital Strata Systems

All modules must obtain equity metrics through this layer.
Prevents shadow equity state across the engine.
"""

from typing import Optional
from engine.performance.pnl_tracker import PnLTracker


class EquityAuthority:
    def __init__(self):
        self._tracker: Optional[PnLTracker] = None

    # --------------------------------------------------------
    # Bind Tracker (called once at system initialization)
    # --------------------------------------------------------

    def bind_tracker(self, tracker: PnLTracker) -> None:
        self._tracker = tracker

    # --------------------------------------------------------
    # Accessors
    # --------------------------------------------------------

    def current_equity(self) -> float:
        self._ensure_bound()
        return self._tracker.current_equity

    def peak_equity(self) -> float:
        self._ensure_bound()
        return self._tracker.peak_equity

    def current_drawdown(self) -> float:
        self._ensure_bound()
        return self._tracker.current_drawdown()

    def max_drawdown(self) -> float:
        self._ensure_bound()
        return self._tracker.max_drawdown

    def total_realized(self) -> float:
        self._ensure_bound()
        return self._tracker.total_realized()

    # --------------------------------------------------------
    # Internal Guard
    # --------------------------------------------------------

    def _ensure_bound(self):
        if self._tracker is None:
            raise RuntimeError("EquityAuthority not bound to PnLTracker")
