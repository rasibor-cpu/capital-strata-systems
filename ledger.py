"""
ledger.py — Trade Lifecycle Ledger (Prompt-Only, No Execution)
--------------------------------------------------------------
Purpose:
- Canonical, append-only ledger for trade intents, tickets, and simulated fills
- Enforces exposure tracking and limit checks
- Produces audit-ready summaries
- NO execution, NO market interaction

Design principles:
- Deterministic
- Side-effect free (except in-memory state)
- Serializable
- Sale-grade governance layer
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime
import uuid


# -----------------------------
# Data Structures
# -----------------------------

@dataclass
class TradeIntent:
    intent_id: str
    symbol: str
    side: str              # "BUY" or "SELL"
    notional: float
    price_hint: Optional[float]
    timestamp: str
    regime: Optional[str]
    rationale: str


@dataclass
class TradeTicket:
    ticket_id: str
    intent_id: str
    approved: bool
    approved_by: Optional[str]
    approval_level: Optional[str]   # AUTO / L1 / L2 / ADMIN
    timestamp: str
    notes: Optional[str] = None


@dataclass
class LedgerEntry:
    entry_id: str
    symbol: str
    side: str
    notional: float
    price: Optional[float]
    intent_id: str
    ticket_id: Optional[str]
    status: str               # INTENT / APPROVED / SIMULATED
    timestamp: str


@dataclass
class PositionState:
    symbol: str
    net_notional: float = 0.0
    gross_notional: float = 0.0


# -----------------------------
# Exposure & Limit Tracker
# -----------------------------

class ExposureTracker:
    def __init__(
        self,
        per_symbol_limit: float,
        gross_limit: float,
    ):
        self.per_symbol_limit = per_symbol_limit
        self.gross_limit = gross_limit
        self.positions: Dict[str, PositionState] = {}

    def apply(self, entry: LedgerEntry) -> Dict[str, bool]:
        symbol = entry.symbol
        delta = entry.notional if entry.side == "BUY" else -entry.notional

        if symbol not in self.positions:
            self.positions[symbol] = PositionState(symbol=symbol)

        pos = self.positions[symbol]
        pos.net_notional += delta
        pos.gross_notional += abs(entry.notional)

        breaches = {
            "per_symbol_breach": abs(pos.net_notional) > self.per_symbol_limit,
            "gross_breach": self.total_gross() > self.gross_limit,
        }
        return breaches

    def total_gross(self) -> float:
        return sum(p.gross_notional for p in self.positions.values())


# -----------------------------
# Ledger Core
# -----------------------------

class TradeLedger:
    def __init__(
        self,
        per_symbol_limit: float = 5_000_000,
        gross_limit: float = 20_000_000,
    ):
        self.entries: List[LedgerEntry] = []
        self.intents: Dict[str, TradeIntent] = {}
        self.tickets: Dict[str, TradeTicket] = {}
        self.exposure = ExposureTracker(
            per_symbol_limit=per_symbol_limit,
            gross_limit=gross_limit,
        )

    # -------- Intents --------

    def register_intent(
        self,
        symbol: str,
        side: str,
        notional: float,
        rationale: str,
        regime: Optional[str] = None,
        price_hint: Optional[float] = None,
    ) -> TradeIntent:
        intent = TradeIntent(
            intent_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            notional=notional,
            price_hint=price_hint,
            timestamp=datetime.utcnow().isoformat(),
            regime=regime,
            rationale=rationale,
        )
        self.intents[intent.intent_id] = intent

        self._append_entry(
            symbol=symbol,
            side=side,
            notional=notional,
            price=price_hint,
            intent_id=intent.intent_id,
            ticket_id=None,
            status="INTENT",
        )
        return intent

    # -------- Approvals --------

    def approve_intent(
        self,
        intent_id: str,
        approved_by: str,
        approval_level: str,
        notes: Optional[str] = None,
    ) -> TradeTicket:
        if intent_id not in self.intents:
            raise ValueError("Unknown intent_id")

        ticket = TradeTicket(
            ticket_id=str(uuid.uuid4()),
            intent_id=intent_id,
            approved=True,
            approved_by=approved_by,
            approval_level=approval_level,
            timestamp=datetime.utcnow().isoformat(),
            notes=notes,
        )
        self.tickets[ticket.ticket_id] = ticket

        intent = self.intents[intent_id]
        self._append_entry(
            symbol=intent.symbol,
            side=intent.side,
            notional=intent.notional,
            price=intent.price_hint,
            intent_id=intent_id,
            ticket_id=ticket.ticket_id,
            status="APPROVED",
        )
        return ticket

    # -------- Simulation --------

    def simulate_fill(
        self,
        ticket_id: str,
        price: Optional[float] = None,
    ) -> Dict[str, bool]:
        if ticket_id not in self.tickets:
            raise ValueError("Unknown ticket_id")

        ticket = self.tickets[ticket_id]
        intent = self.intents[ticket.intent_id]

        entry = self._append_entry(
            symbol=intent.symbol,
            side=intent.side,
            notional=intent.notional,
            price=price,
            intent_id=intent.intent_id,
            ticket_id=ticket.ticket_id,
            status="SIMULATED",
        )
        return self.exposure.apply(entry)

    # -------- Internal --------

    def _append_entry(
        self,
        symbol: str,
        side: str,
        notional: float,
        price: Optional[float],
        intent_id: str,
        ticket_id: Optional[str],
        status: str,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            notional=notional,
            price=price,
            intent_id=intent_id,
            ticket_id=ticket_id,
            status=status,
            timestamp=datetime.utcnow().isoformat(),
        )
        self.entries.append(entry)
        return entry

    # -------- Reporting --------

    def snapshot(self) -> Dict:
        return {
            "positions": {
                sym: asdict(pos) for sym, pos in self.exposure.positions.items()
            },
            "gross_exposure": self.exposure.total_gross(),
            "entries": [asdict(e) for e in self.entries],
        }
