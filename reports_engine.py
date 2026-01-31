"""
reports_engine.py — Ledger Reports & Breach Alerts (Prompt-Only)
----------------------------------------------------------------
Purpose:
- Generate treasury-grade reports from TradeLedger (signals side)
- Generate customer posting reports from PostingLedger (posting side)
- Produce detailed breach records including customer + ledger + transaction context
- Emit supervisor alert payloads (stub only; no messaging)

Compatibility:
- ReportsEngine(ledger) still works (demo runner unchanged)
- If a PostingLedger is supplied, customer/ledger/transaction details are populated
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
    symbol: str                   # symbol or pair or descriptor
    side: str                     # BUY / SELL / DR / CR
    currency: Optional[str]       # e.g. USD, NGN (posting) or None (trade-ledger)
    fx_pair: Optional[str]        # e.g. USDNGN (posting) or None
    notional: float
    price: Optional[float]
    value_date: Optional[str]
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
    def __init__(
        self,
        ledger: Any,
        posting_ledger: Optional[Any] = None,
        per_customer_limit: float = 2_000_000,
        per_ledger_limit: float = 10_000_000,
    ):
        """
        ledger: instance of TradeLedger (signals/intent/tickets/fills)
        posting_ledger: instance of PostingLedger (customer postings) or None
        per_customer_limit: max cumulative abs(notional) per customer over snapshot window
        per_ledger_limit: max cumulative abs(notional) per ledger_id over snapshot window

        Note: These are snapshot-window controls (in-memory demo). For production,
        limits become time-bucketed + persistent + role-based approvals.
        """
        self.ledger = ledger
        self.posting_ledger = posting_ledger
        self.per_customer_limit = float(per_customer_limit)
        self.per_ledger_limit = float(per_ledger_limit)

    # -------------------------
    # Standard TradeLedger Reports
    # -------------------------

    def report_open_intents(self) -> List[Dict]:
        return [asdict(e) for e in self.ledger.entries if e.status == "INTENT"]

    def report_approved_tickets(self) -> List[Dict]:
        return [asdict(e) for e in self.ledger.entries if e.status == "APPROVED"]

    def report_simulated_fills(self) -> List[Dict]:
        return [asdict(e) for e in self.ledger.entries if e.status == "SIMULATED"]

    def report_positions(self) -> Dict[str, Dict]:
        return {symbol: asdict(pos) for symbol, pos in self.ledger.exposure.positions.items()}

    def report_gross_exposure(self) -> float:
        return self.ledger.exposure.total_gross()

    # -------------------------
    # PostingLedger Reports (if available)
    # -------------------------

    def report_customer_postings(self) -> List[Dict]:
        if not self.posting_ledger:
            return []
        # posting_ledger.snapshot() already returns dicts; keep consistent
        try:
            return self.posting_ledger.snapshot()
        except Exception:
            # fallback if snapshot not present
            return [asdict(e) for e in getattr(self.posting_ledger, "entries", [])]

    # -------------------------
    # Breach Detection (TradeLedger + PostingLedger)
    # -------------------------

    def detect_breaches(self) -> List[BreachRecord]:
        breaches: List[BreachRecord] = []

        # A) TradeLedger breaches (per-symbol and gross)
        breaches.extend(self._detect_trade_ledger_breaches())

        # B) PostingLedger breaches (customer + ledger limits)
        if self.posting_ledger:
            breaches.extend(self._detect_posting_ledger_breaches())

        return breaches

    def _detect_trade_ledger_breaches(self) -> List[BreachRecord]:
        breaches: List[BreachRecord] = []

        for entry in self.ledger.entries:
            symbol_pos = self.ledger.exposure.positions.get(entry.symbol)
            if not symbol_pos:
                continue

            # Per-symbol breach
            if abs(symbol_pos.net_notional) > self.ledger.exposure.per_symbol_limit:
                breaches.append(
                    self._build_trade_breach(
                        breach_type="PER_SYMBOL",
                        severity="HIGH",
                        entry=entry,
                        observed=abs(symbol_pos.net_notional),
                        limit=self.ledger.exposure.per_symbol_limit,
                        recommended="Reduce position or escalate for override",
                        escalation="L1",
                    )
                )

            # Gross breach (evaluate on current snapshot)
            total_gross = self.ledger.exposure.total_gross()
            if total_gross > self.ledger.exposure.gross_limit:
                breaches.append(
                    self._build_trade_breach(
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

    def _detect_posting_ledger_breaches(self) -> List[BreachRecord]:
        breaches: List[BreachRecord] = []

        entries = getattr(self.posting_ledger, "entries", [])
        if not entries:
            return breaches

        # Snapshot-window aggregates
        by_customer: Dict[str, float] = {}
        by_ledger: Dict[str, float] = {}

        for e in entries:
            by_customer[e.customer_id] = by_customer.get(e.customer_id, 0.0) + abs(float(e.notional))
            by_ledger[e.ledger_id] = by_ledger.get(e.ledger_id, 0.0) + abs(float(e.notional))

        # Emit breaches per entry so reports carry the specific transaction details
        for e in entries:
            cust_total = by_customer.get(e.customer_id, 0.0)
            led_total = by_ledger.get(e.ledger_id, 0.0)

            if cust_total > self.per_customer_limit:
                breaches.append(
                    self._build_posting_breach(
                        breach_type="CUSTOMER_LIMIT",
                        severity="HIGH",
                        posting_entry=e,
                        observed=cust_total,
                        limit=self.per_customer_limit,
                        recommended="Hold posting and escalate for approval / split booking",
                        escalation="L1",
                    )
                )

            if led_total > self.per_ledger_limit:
                breaches.append(
                    self._build_posting_breach(
                        breach_type="LEDGER_LIMIT",
                        severity="CRITICAL",
                        posting_entry=e,
                        observed=led_total,
                        limit=self.per_ledger_limit,
                        recommended="Freeze ledger posting and notify control desk",
                        escalation="ADMIN",
                    )
                )

        return breaches

    # -------------------------
    # Builders (Trade vs Posting)
    # -------------------------

    def _build_trade_breach(
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
            breach_id=f"BR-TRADE-{entry.entry_id}",
            breach_type=breach_type,
            severity=severity,

            # No customer context on signal ledger by default
            customer_id=None,
            customer_name=None,
            account_ref=None,

            # Ledger context (trade ledger)
            ledger_type="TREASURY",
            ledger_id="TRADE_LEDGER",
            entry_id=entry.entry_id,
            intent_id=entry.intent_id,
            ticket_id=entry.ticket_id,

            # Transaction context
            transaction_type="FX",
            symbol=entry.symbol,
            side=entry.side,
            currency=None,
            fx_pair=None,
            notional=float(entry.notional),
            price=entry.price,
            value_date=None,
            timestamp=entry.timestamp,

            # Limit context
            limit_value=float(limit),
            observed_value=float(observed),

            # Governance
            recommended_action=recommended,
            escalation_level=escalation,
            reported_at=datetime.utcnow().isoformat(),
        )

    def _build_posting_breach(
        self,
        breach_type: str,
        severity: str,
        posting_entry: Any,
        observed: float,
        limit: float,
        recommended: str,
        escalation: str,
    ) -> BreachRecord:
        # posting_entry is PostingEntry from posting_ledger.py
        return BreachRecord(
            breach_id=f"BR-POST-{posting_entry.entry_id}",
            breach_type=breach_type,
            severity=severity,

            # Customer context (FILLED)
            customer_id=posting_entry.customer_id,
            customer_name=posting_entry.customer_name,
            account_ref=posting_entry.account_ref,

            # Ledger context (FILLED)
            ledger_type=posting_entry.ledger_type,
            ledger_id=posting_entry.ledger_id,
            entry_id=posting_entry.entry_id,
            intent_id=None,
            ticket_id=None,

            # Transaction context (FILLED)
            transaction_type=posting_entry.transaction_type,
            symbol=posting_entry.fx_pair or posting_entry.currency,
            side=posting_entry.side,
            currency=posting_entry.currency,
            fx_pair=posting_entry.fx_pair,
            notional=float(posting_entry.notional),
            price=posting_entry.price,
            value_date=posting_entry.value_date,
            timestamp=posting_entry.booking_date,

            # Limit context
            limit_value=float(limit),
            observed_value=float(observed),

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
