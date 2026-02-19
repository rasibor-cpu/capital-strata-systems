"""
Instrument Performance Ledger
Capital Strata Systems

Tracks:
- PnL per instrument
- PnL per time bucket (weekly / monthly / quarterly / annual)
- Aggregated totals

Pure in-memory structure.
Deterministic.
No external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


# -----------------------------------------------------------
# Time Bucket Helpers
# -----------------------------------------------------------

def _week_key(dt: datetime) -> str:
    return f"{dt.year}-W{dt.isocalendar().week}"

def _month_key(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"

def _quarter_key(dt: datetime) -> str:
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{q}"

def _year_key(dt: datetime) -> str:
    return f"{dt.year}"


# -----------------------------------------------------------
# Ledger
# -----------------------------------------------------------

@dataclass
class InstrumentPerformanceLedger:

    # instrument → pnl
    total_by_instrument: Dict[str, float] = field(default_factory=dict)

    # time bucket → instrument → pnl
    weekly: Dict[str, Dict[str, float]] = field(default_factory=dict)
    monthly: Dict[str, Dict[str, float]] = field(default_factory=dict)
    quarterly: Dict[str, Dict[str, float]] = field(default_factory=dict)
    annual: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # -------------------------------------------------------

    def record_trade(
        self,
        *,
        instrument: str,
        pnl: float,
        timestamp: datetime,
    ) -> None:

        instrument = str(instrument)
        pnl = float(pnl)

        # --- total ---
        self.total_by_instrument[instrument] = (
            self.total_by_instrument.get(instrument, 0.0) + pnl
        )

        # --- weekly ---
        w_key = _week_key(timestamp)
        self.weekly.setdefault(w_key, {})
        self.weekly[w_key][instrument] = (
            self.weekly[w_key].get(instrument, 0.0) + pnl
        )

        # --- monthly ---
        m_key = _month_key(timestamp)
        self.monthly.setdefault(m_key, {})
        self.monthly[m_key][instrument] = (
            self.monthly[m_key].get(instrument, 0.0) + pnl
        )

        # --- quarterly ---
        q_key = _quarter_key(timestamp)
        self.quarterly.setdefault(q_key, {})
        self.quarterly[q_key][instrument] = (
            self.quarterly[q_key].get(instrument, 0.0) + pnl
        )

        # --- annual ---
        y_key = _year_key(timestamp)
        self.annual.setdefault(y_key, {})
        self.annual[y_key][instrument] = (
            self.annual[y_key].get(instrument, 0.0) + pnl
        )

    # -------------------------------------------------------

    def get_total(self, instrument: str) -> float:
        return self.total_by_instrument.get(instrument, 0.0)

    def snapshot(self) -> Dict[str, Dict]:
        return {
            "total_by_instrument": dict(self.total_by_instrument),
            "weekly": dict(self.weekly),
            "monthly": dict(self.monthly),
            "quarterly": dict(self.quarterly),
            "annual": dict(self.annual),
        }
