"""
reports_engine.py — Ledger Reports & Breach Alerts (Prompt-Only)
----------------------------------------------------------------
Purpose:
- Generate treasury-grade reports from the canonical TradeLedger
- Produce detailed breach records including customer + ledger context
- Emit supervisor alert payloads (stub only; no messaging)

Design:
- Deterministic
- Read-only over ledger state
- Sale-grade audit clarity
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime


# -----------------------------
# Breach Record
# -----------------------------

@dataclass
class BreachRecord:
    breach_id: str
    breach_type: str              # PER_SYMBOL / GROSS / CUSTOMER_LIMIT / LEDGER_LIMIT
    severity: str                 # LOW / MEDIUM / HIGH / CRITICAL

    # Customer context (optional)
    customer_id: Optional[str]
    customer_name: Optional[str]
    account_ref: Optional[str]

    # Ledger context
    ledger_type: str              # CUSTOMER / TREASURY / INTERNAL
    ledger_id: str
    entry_id: str
    intent_id: Optional[str]
    ticket_id: Optional[str]

    # Transaction context
    transaction_type: str         # POSTING / FX / TRANSFER / ADJUSTMENT
    symbol: str
    side: str                     # BUY / SELL / DR / CR
    notional: float
    price: Optional[float]
    timestamp: str

    # Limit context
    limit_value: float
    observed_value: float

    # Governance
    recommended_action: str
    escalation_level: str         # AUTO / L1 / L2 / ADMIN
    reported_at: str


# -----------------------------
# Report Engine
# -----------------------------

class ReportsEngine:
    def __init__(self, ledger: Any):
        """
        ledger: instance of TradeLedger (import avoided for loose coupling)
        """
        self.ledger = ledger

    # -------------------------
    # Standard Reports
    # -------------------------

    def report_open_intents(self) -> List[Dict]:
        return [
            asdict(e)
            for e in self.ledger.entries
            if e.status == "INTENT"
        ]

    def report_approved_tickets(self) -> List[Dict]:
        return [
            asdict(e)
            for e in self.ledger.entries
            if e.status == "APPROVED"
        ]

    def report_simulated_fills(self) -> List[Dict]:
        return [
            asdict(e)
            for e in self.ledger.entries
            if e.status == "SIMULATED"
        ]

    def report_positions(self) -> Dict[str, Dict]:
        return {
            symbol: asdict(pos)
            for symbol, pos in self.ledger.exposure.positions.items()
        }

    def report_gross_exposure(self) -> float:
        return self.ledger.exposure.total_gross()

    # -------------------------
    # Breach Detection
    # -------------------------

    def detect_breaches(self) -> List[BreachRecord]:
        breaches: List[BreachRecord] = []

        for entry in self.ledger.entries:
            symbol_pos = self.ledger.exposure.positions.get(entry.symbol)
            if not symbol_pos:
                continue

            # Per-symbol breach
            if abs(symbol_pos.net_notional) > self.ledger.exposure.per_symbol_limit:
                breaches.append(
                    self._build_breach(
                        breach_type="PER_SYMBOL",
                        severity="HIGH",
                        entry=entry,
                        observed=abs(symbol_pos.net_notional),
                        limit=self.ledger.exposure.per_symbol_limit,
                        recommended="Reduce position or escalate for override",
                        escalation="L1",
                    )
                )

            # Gross breach
            total_gross = self.ledger.exposure.total_gross()
            if total_gross > self.ledger.exposure.gross_limit:
                breaches.append(
                    self._build_breach(
                        breach_type="GROSS",
                        severity="CRITICAL",
                        entry=entry,
                        observed=total_gross,
                        limit=self.ledger.exposure.gross_limit,
                        recommended="Freeze trading and notify risk committee",
                        escalation="ADMIN",
                    )
                )

        return breaches

    # -------------------------
    # Internal
    # -------------------------

    def _build_breach(
        self,
        breach_type: str,
        severity: str,
        entry: Any,
        observed: float,
        limit: float,
        recommended: str,
        escalation: str,
    ) -> BreachRecord:

        return BreachRecord(
            breach_id=f"BR-{entry.entry_id}",
            breach_type=breach_type,
            severity=severity,

            # Customer context (stub — populated when customer posting is wired)
            customer_id=None,
            customer_name=None,
            account_ref=None,

            # Ledger context
            ledger_type="TREASURY",
            ledger_id="MAIN_LEDGER",
            entry_id=entry.entry_id,
            intent_id=entry.intent_id,
            ticket_id=entry.ticket_id,

            # Transaction context
            transaction_type="FX",
            symbol=entry.symbol,
            side=entry.side,
            notional=entry.notional,
            price=entry.price,
            timestamp=entry.timestamp,

            # Limit context
            limit_value=limit,
            observed_value=observed,

            # Governance
            recommended_action=recommended,
            escalation_level=escalation,
            reported_at=datetime.utcnow().isoformat(),
        )

    # -------------------------
    # Supervisor Alert Payload
    # -------------------------

    def supervisor_alerts(self) -> List[Dict]:
        return [asdict(b) for b in self.detect_breaches()]
