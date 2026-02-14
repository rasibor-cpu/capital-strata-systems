"""
Capital Strata Systems
Futures Capital Bucket Manager – Phase 2A

Purpose:
Track and enforce 25% allocation cap for Futures.
No execution logic included.
"""

from __future__ import annotations
from dataclasses import dataclass


FX_ALLOCATION = 0.75
FUTURES_ALLOCATION = 0.25


@dataclass
class CapitalBuckets:
    total_equity: float
    fx_equity: float
    futures_equity: float


class FuturesCapitalBucket:

    def __init__(self, total_equity: float):
        self.total_equity = total_equity

    # ---------------------------------------------------
    # Allocation Calculations
    # ---------------------------------------------------

    def max_fx_capital(self) -> float:
        return self.total_equity * FX_ALLOCATION

    def max_futures_capital(self) -> float:
        return self.total_equity * FUTURES_ALLOCATION

    # ---------------------------------------------------
    # Exposure Validation
    # ---------------------------------------------------

    def futures_within_limit(self, proposed_exposure: float) -> bool:
        """
        Ensures proposed futures exposure does not exceed 25% allocation.
        """
        return proposed_exposure <= self.max_futures_capital()

    def fx_within_limit(self, proposed_exposure: float) -> bool:
        """
        Ensures FX exposure does not exceed 75% allocation.
        """
        return proposed_exposure <= self.max_fx_capital()

    # ---------------------------------------------------
    # Snapshot
    # ---------------------------------------------------

    def snapshot(self) -> CapitalBuckets:
        return CapitalBuckets(
            total_equity=self.total_equity,
            fx_equity=self.max_fx_capital(),
            futures_equity=self.max_futures_capital(),
        )
