from __future__ import annotations

"""
MT5 Trade Ticket Exporter (Manual Execution Path)

Purpose:
- Convert internal trade tickets into a clean CSV format
- Designed for fast manual entry into MT5 demo
- One row per ticket, append-only
- No broker API, no KYC dependency

This file is SAFE and OFFLINE.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import csv
import os


@dataclass
class MT5Ticket:
    time_utc: str
    symbol: str
    side: str              # BUY / SELL
    volume_lots: float
    price_snapshot: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str


class MT5TicketExporter:
    def __init__(self, csv_path: str = "out/mt5_trade_tickets.csv") -> None:
        self.csv_path = csv_path
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    def export(self, ticket: MT5Ticket) -> None:
        file_exists = os.path.exists(self.csv_path)

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=list(asdict(ticket).keys())
            )

            if not file_exists:
                writer.writeheader()

            writer.writerow(asdict(ticket))


def lots_from_units(units: int) -> float:
    """
    FX heuristic:
    - 100,000 units = 1.0 lot
    - 10,000 units  = 0.10 lot
    - 1,000 units   = 0.01 lot
    """
    return round(units / 100_000.0, 2)


def make_mt5_ticket(
    instrument: str,
    side: str,
    units: int,
    price_snapshot: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    reason: str,
) -> MT5Ticket:
    symbol = instrument.replace("_", "")
    return MT5Ticket(
        time_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        symbol=symbol,
        side=side.upper(),
        volume_lots=lots_from_units(units),
        price_snapshot=price_snapshot,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
    )