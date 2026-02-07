"""
P&L Reporting Engine – Extended Transaction View
REA Capital Trading Engine

Provides:
- Daily / WTD / MTD / YTD summaries
- Custom date range summaries
- Detailed transaction summaries
- Cumulative P&L tracking within selected period
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Tuple


DEFAULT_LEDGER_PATH = os.getenv(
    "REA_PNL_LEDGER_PATH",
    "reporting_store/pnl_ledger.jsonl"
)


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _load_events(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line.strip()))
            except Exception:
                continue
    return events


@dataclass
class Summary:
    label: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    pnl: float
    fees: float


def _filter_period(events: List[dict], start: datetime, end: datetime) -> List[dict]:
    return [
        e for e in events
        if start <= _parse_ts(e["ts_utc"]) < end
    ]


def _summarize(events: List[dict], label: str) -> Summary:
    trades = len(events)
    pnl = sum(float(e.get("pnl", 0.0)) for e in events)
    fees = sum(float(e.get("fees", 0.0)) for e in events)

    wins = sum(1 for e in events if float(e.get("pnl", 0.0)) > 0)
    losses = sum(1 for e in events if float(e.get("pnl", 0.0)) < 0)
    win_rate = wins / trades if trades else 0.0

    return Summary(label, trades, wins, losses, win_rate, pnl, fees)


# ------------------------------------------------
# PUBLIC REPORT FUNCTIONS
# ------------------------------------------------

def today() -> Tuple[Summary, List[dict]]:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now
    events = _filter_period(_load_events(DEFAULT_LEDGER_PATH), start, end)
    return _summarize(events, "TODAY (UTC)"), events


def wtd() -> Tuple[Summary, List[dict]]:
    now = datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()

    events = []
    for e in _load_events(DEFAULT_LEDGER_PATH):
        dt = _parse_ts(e["ts_utc"])
        y, w, _ = dt.isocalendar()
        if y == iso_year and w == iso_week:
            events.append(e)

    return _summarize(events, "WTD (UTC ISO)"), events


def mtd() -> Tuple[Summary, List[dict]]:
    now = datetime.now(timezone.utc)
    events = []
    for e in _load_events(DEFAULT_LEDGER_PATH):
        dt = _parse_ts(e["ts_utc"])
        if dt.year == now.year and dt.month == now.month:
            events.append(e)

    return _summarize(events, "MTD (UTC)"), events


def ytd() -> Tuple[Summary, List[dict]]:
    now = datetime.now(timezone.utc)
    events = []
    for e in _load_events(DEFAULT_LEDGER_PATH):
        dt = _parse_ts(e["ts_utc"])
        if dt.year == now.year:
            events.append(e)

    return _summarize(events, "YTD (UTC)"), events


def custom_range(start_iso: str, end_iso: str) -> Tuple[Summary, List[dict]]:
    start = datetime.fromisoformat(start_iso).astimezone(timezone.utc)
    end = datetime.fromisoformat(end_iso).astimezone(timezone.utc)

    events = _filter_period(_load_events(DEFAULT_LEDGER_PATH), start, end)
    return _summarize(events, f"RANGE {start_iso} → {end_iso}"), events


# ------------------------------------------------
# PRINT FUNCTIONS
# ------------------------------------------------

def print_summary(summary: Summary):
    print(f"\n=== {summary.label} ===")
    print(f"Trades:   {summary.trades}")
    print(f"Wins:     {summary.wins}")
    print(f"Losses:   {summary.losses}")
    print(f"Win rate: {summary.win_rate:.2%}")
    print(f"PnL:      {summary.pnl:.2f}")
    print(f"Fees:     {summary.fees:.2f}")


def print_transaction_details(events: List[dict]):
    print("\n--- TRANSACTION DETAILS ---")
    cumulative = 0.0

    for i, e in enumerate(events, 1):
        pnl = float(e.get("pnl", 0.0))
        cumulative += pnl

        print(f"\nTrade #{i}")
        print(f"Trade Type:      {e.get('trade_type', '')}")
        print(f"Symbol:          {e.get('symbol', '')}")
        print(f"Side:            {e.get('side', '')}")
        print(f"Execution Date:  {e.get('execution_date', '')}")
        print(f"Value Date:      {e.get('value_date', '')}")
        print(f"Amount:          {e.get('amount', 0.0)} {e.get('currency', '')}")
        print(f"FX Rate:         {e.get('fx_rate', 1.0)}")
        print(f"Exchange Text:   {e.get('exchange_rate_text', '')}")
        print(f"Entry Px:        {e.get('entry_px', 0.0)}")
        print(f"Exit Px:         {e.get('exit_px', 0.0)}")
        print(f"Fees:            {e.get('fees', 0.0)}")
        print(f"Trade P&L:       {pnl:.2f}")
        print(f"Cumulative P&L:  {cumulative:.2f}")
