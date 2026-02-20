"""
PnLTracker – Institutional Performance Ledger
Capital Strata Systems (CSS)

Authoritative equity spine.

Features:
- Multi-instrument PnL separation
- Realized vs Unrealized tracking
- Time-bucket aggregation (weekly, monthly, quarterly, annual)
- Drawdown tracking
- Append-only journal integrity
- Weekly snapshot support for AssetAllocator
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import uuid


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class JournalEntry:
    entry_id: str
    instrument: str
    timestamp: datetime
    realized_pnl: float
    unrealized_pnl: float
    equity_after: float


@dataclass
class InstrumentLedger:
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trades: int = 0


# ============================================================
# CORE TRACKER
# ============================================================

class PnLTracker:

    def __init__(self, starting_equity: float):

        self.starting_equity = starting_equity
        self.current_equity = starting_equity
        self.peak_equity = starting_equity
        self.max_drawdown = 0.0

        self.instrument_ledgers: Dict[str, InstrumentLedger] = {}
        self.journal: List[JournalEntry] = []

        # time buckets (net totals)
        self.weekly = defaultdict(float)
        self.monthly = defaultdict(float)
        self.quarterly = defaultdict(float)
        self.annual = defaultdict(float)

    # ========================================================
    # RECORD TRADE
    # ========================================================

    def record_trade(
        self,
        instrument: str,
        realized_pnl: float,
        unrealized_pnl: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> None:

        timestamp = timestamp or datetime.utcnow()

        # instrument ledger
        ledger = self.instrument_ledgers.setdefault(
            instrument, InstrumentLedger()
        )

        ledger.realized_pnl += realized_pnl
        ledger.unrealized_pnl = unrealized_pnl
        ledger.trades += 1

        # equity update (realized only)
        self.current_equity += realized_pnl

        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, drawdown)

        # time keys
        week_key = f"{timestamp.year}-W{timestamp.isocalendar().week}"
        month_key = f"{timestamp.year}-{timestamp.month}"
        quarter_key = f"{timestamp.year}-Q{((timestamp.month-1)//3)+1}"
        year_key = f"{timestamp.year}"

        self.weekly[week_key] += realized_pnl
        self.monthly[month_key] += realized_pnl
        self.quarterly[quarter_key] += realized_pnl
        self.annual[year_key] += realized_pnl

        # append-only journal
        self.journal.append(
            JournalEntry(
                entry_id=str(uuid.uuid4()),
                instrument=instrument,
                timestamp=timestamp,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                equity_after=self.current_equity,
            )
        )

    # ========================================================
    # SNAPSHOT FOR ALLOCATOR (WEEKLY)
    # ========================================================

    def weekly_snapshot(self) -> Dict[str, Dict[str, float]]:
        """
        Returns allocator-compatible structure:

        {
            "weekly_instrument_totals": {...},
            "weekly_instrument_abs_totals": {...},
            "weekly_asset_totals": {...},
            "weekly_asset_abs_totals": {...},
        }

        Asset class mapping:
        - Currently simple default: everything = "FX"
        - Later replace with instrument registry
        """

        if not self.journal:
            return {}

        # find latest week in journal
        latest_week = None
        for entry in reversed(self.journal):
            latest_week = f"{entry.timestamp.year}-W{entry.timestamp.isocalendar().week}"
            break

        if latest_week is None:
            return {}

        instrument_net = defaultdict(float)
        instrument_abs = defaultdict(float)

        asset_net = defaultdict(float)
        asset_abs = defaultdict(float)

        for entry in self.journal:
            wk = f"{entry.timestamp.year}-W{entry.timestamp.isocalendar().week}"
            if wk != latest_week:
                continue

            pnl = float(entry.realized_pnl)
            instrument_net[entry.instrument] += pnl
            instrument_abs[entry.instrument] += abs(pnl)

            # simple FX default mapping
            asset_class = "FX"
            asset_net[asset_class] += pnl
            asset_abs[asset_class] += abs(pnl)

        return {
            "weekly_instrument_totals": dict(instrument_net),
            "weekly_instrument_abs_totals": dict(instrument_abs),
            "weekly_asset_totals": dict(asset_net),
            "weekly_asset_abs_totals": dict(asset_abs),
        }

    # ========================================================
    # METRICS
    # ========================================================

    def total_realized(self) -> float:
        return self.current_equity - self.starting_equity

    def current_drawdown(self) -> float:
        if self.peak_equity == 0:
            return 0.0
        return (self.peak_equity - self.current_equity) / self.peak_equity

    def instrument_summary(self) -> Dict[str, Dict]:
        summary = {}
        for instrument, ledger in self.instrument_ledgers.items():
            summary[instrument] = {
                "realized_pnl": ledger.realized_pnl,
                "unrealized_pnl": ledger.unrealized_pnl,
                "trades": ledger.trades,
            }
        return summary

    def equity_snapshot(self) -> Dict[str, float]:
        return {
            "starting_equity": self.starting_equity,
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown(),
            "total_realized": self.total_realized(),
        }
