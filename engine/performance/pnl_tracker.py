"""
PnLTracker – Institutional Performance Ledger v2
Capital Strata Systems (CSS)

Upgrades:
- Rolling weekly window
- Instrument performance classification
- Rebalancing signal generation
- Capital weight suggestion logic
- Institutional reporting spine
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timezone
from collections import defaultdict
import uuid


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

        # time buckets
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

        timestamp = timestamp or _utc_now()

        ledger = self.instrument_ledgers.setdefault(
            instrument, InstrumentLedger()
        )

        ledger.realized_pnl += realized_pnl
        ledger.unrealized_pnl = unrealized_pnl
        ledger.trades += 1

        # equity update
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

        # journal append
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
    # WEEK IDENTIFICATION
    # ========================================================

    def _latest_week_key(self) -> Optional[str]:
        if not self.journal:
            return None
        entry = self.journal[-1]
        return f"{entry.timestamp.year}-W{entry.timestamp.isocalendar().week}"

    # ========================================================
    # WEEKLY SNAPSHOT + CLASSIFICATION
    # ========================================================

    def weekly_snapshot(self) -> Dict:

        latest_week = self._latest_week_key()
        if not latest_week:
            return {}

        instrument_net = defaultdict(float)
        instrument_abs = defaultdict(float)

        for entry in self.journal:
            wk = f"{entry.timestamp.year}-W{entry.timestamp.isocalendar().week}"
            if wk != latest_week:
                continue

            pnl = float(entry.realized_pnl)
            instrument_net[entry.instrument] += pnl
            instrument_abs[entry.instrument] += abs(pnl)

        classification = {}
        for inst, pnl in instrument_net.items():
            if pnl > 0:
                status = "WINNING"
            elif pnl < 0:
                status = "LOSING"
            else:
                status = "FLAT"

            classification[inst] = {
                "net_pnl": pnl,
                "abs_pnl": instrument_abs[inst],
                "status": status,
            }

        return {
            "week": latest_week,
            "instrument_performance": classification,
            "portfolio_net": sum(instrument_net.values()),
        }

    # ========================================================
    # ROLLING 4-WEEK PERFORMANCE
    # ========================================================

    def rolling_4week_summary(self) -> Dict[str, float]:

        if not self.journal:
            return {}

        weeks = sorted(set(
            f"{e.timestamp.year}-W{e.timestamp.isocalendar().week}"
            for e in self.journal
        ))

        last_4 = weeks[-4:]

        summary = defaultdict(float)

        for entry in self.journal:
            wk = f"{entry.timestamp.year}-W{entry.timestamp.isocalendar().week}"
            if wk in last_4:
                summary[entry.instrument] += entry.realized_pnl

        return dict(summary)

    # ========================================================
    # REBALANCING SIGNAL ENGINE
    # ========================================================

    def rebalancing_signal(self) -> Dict[str, float]:
        """
        Suggest capital tilt based on rolling 4-week performance.
        Winning instruments gain weight.
        Losing instruments lose weight.
        """

        perf = self.rolling_4week_summary()
        if not perf:
            return {}

        total_abs = sum(abs(v) for v in perf.values())
        if total_abs == 0:
            return {k: 0.0 for k in perf.keys()}

        weights = {}
        for inst, pnl in perf.items():
            weights[inst] = pnl / total_abs

        return weights

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
