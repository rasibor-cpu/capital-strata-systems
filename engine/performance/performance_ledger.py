"""
Performance Ledger
==================

Multi-Asset, Multi-Period Performance Tracking
Capital Strata Systems / REA

Design Principles:
- UTC internal time
- Instrument-level tracking
- Asset-class aggregation
- Weekly reconciliation support
- No direct mutation of master equity
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from collections import defaultdict


# ============================================================
# Trade Record
# ============================================================

@dataclass(frozen=True)
class TradeRecord:
    timestamp: datetime
    instrument: str
    asset_class: str
    pnl: float


# ============================================================
# Performance Ledger
# ============================================================

class PerformanceLedger:

    def __init__(self) -> None:
        self._trades: List[TradeRecord] = []

        # Aggregations
        self._instrument_totals: Dict[str, float] = defaultdict(float)
        self._asset_totals: Dict[str, float] = defaultdict(float)

        # Weekly aggregation (ISO calendar week boundary based on UTC)
        self._weekly_asset_totals: Dict[str, float] = defaultdict(float)

    # ========================================================
    # Core Recording
    # ========================================================

    def record_trade(
        self,
        *,
        instrument: str,
        asset_class: str,
        pnl: float,
        timestamp: Optional[datetime] = None,
    ) -> None:

        ts = timestamp or datetime.now(timezone.utc)

        record = TradeRecord(
            timestamp=ts,
            instrument=instrument,
            asset_class=asset_class,
            pnl=float(pnl),
        )

        self._trades.append(record)

        # Update totals
        self._instrument_totals[instrument] += pnl
        self._asset_totals[asset_class] += pnl

        # Weekly (UTC Monday reset logic handled externally)
        self._weekly_asset_totals[asset_class] += pnl

    # ========================================================
    # Query Methods
    # ========================================================

    def get_total_by_instrument(self, instrument: str) -> float:
        return float(self._instrument_totals.get(instrument, 0.0))

    def get_total_by_asset_class(self, asset_class: str) -> float:
        return float(self._asset_totals.get(asset_class, 0.0))

    def get_weekly_pnl(self, asset_class: Optional[str] = None) -> float:
        if asset_class:
            return float(self._weekly_asset_totals.get(asset_class, 0.0))
        return float(sum(self._weekly_asset_totals.values()))

    # ========================================================
    # Reconciliation Logic
    # ========================================================

    def reconcile_week(self, asset_class: str) -> float:
        """
        Returns weekly PnL for asset class and resets that bucket.
        Does NOT mutate master equity.
        """
        pnl = float(self._weekly_asset_totals.get(asset_class, 0.0))
        self._weekly_asset_totals[asset_class] = 0.0
        return pnl

    # ========================================================
    # Snapshot
    # ========================================================

    def snapshot(self) -> Dict[str, Any]:
        return {
            "instrument_totals": dict(self._instrument_totals),
            "asset_totals": dict(self._asset_totals),
            "weekly_asset_totals": dict(self._weekly_asset_totals),
            "trade_count": len(self._trades),
        }
