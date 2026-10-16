"""Paper order management system (PAPER ONLY - no live venue adapter exists here).

The OMS executes what the governed router already authorised and never widens it:

* one immediate-or-cancel market order per COPIED decision, keyed by a deterministic
  client_order_id; resubmitting the same id is idempotent, a conflicting reuse is refused;
* strict state machine NEW -> ACK -> PARTIALLY_FILLED -> FILLED, or REJECTED / CANCELLED,
  with UNKNOWN when the venue connection drops mid-submit (never assumed filled or failed);
* only the venue's reported fills count (quantity and price, incl. slippage); unfilled
  remainder is cancelled (IOC);
* reconcile() resolves UNKNOWN / open orders from the venue's own records and reports
  quantity mismatches and venue orders the OMS does not know (orphans);
* emergency_shutdown() persists a halt, cancels every open order at the venue and blocks
  all new submissions; resume requires a SUPER_USER and a clean reconciliation.

Every transition is appended to a hash-chained journal.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from backend.certification.ov002_persistence import PersistenceError, atomic_write_json, read_json_object
from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.hash_chain import HashChainLog

OMS_SCHEMA = "css.oms.paper.v1"
ADMIN_ROLE = "SUPER_USER"


class OMSError(RuntimeError):
    pass


class VenueDisconnected(ConnectionError):
    pass


class OrderState(str, Enum):
    NEW = "NEW"
    ACK = "ACK"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


TERMINAL = {OrderState.FILLED, OrderState.REJECTED, OrderState.CANCELLED}
_ALLOWED = {
    OrderState.NEW: {OrderState.ACK, OrderState.REJECTED, OrderState.UNKNOWN, OrderState.FILLED,
                     OrderState.PARTIALLY_FILLED, OrderState.CANCELLED},
    OrderState.ACK: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED,
                     OrderState.UNKNOWN},
    OrderState.PARTIALLY_FILLED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED,
                                  OrderState.UNKNOWN},
    OrderState.UNKNOWN: {OrderState.ACK, OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED,
                         OrderState.REJECTED, OrderState.UNKNOWN},
}


@dataclass(frozen=True)
class OrderIntent:
    client_order_id: str
    user_id: str
    symbol: str
    side: str  # BUY | SELL
    quantity: float
    reference_price: float

    def check(self) -> None:
        if not self.client_order_id or len(self.client_order_id) > 64:
            raise OMSError("client_order_id_invalid")
        if self.side not in {"BUY", "SELL"}:
            raise OMSError("side_invalid")
        for v in (self.quantity, self.reference_price):
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
                raise OMSError("quantity_or_price_invalid")


@dataclass(frozen=True)
class VenueReport:
    """The venue's own record of an order (what reconciliation trusts)."""
    client_order_id: str
    venue_order_id: str
    status: str  # ACK | PARTIALLY_FILLED | FILLED | REJECTED | CANCELLED
    filled_qty: float = 0.0
    avg_price: float | None = None
    reason: str = ""


class Venue(Protocol):
    name: str

    def submit(self, intent: OrderIntent) -> VenueReport: ...
    def status(self, client_order_id: str) -> VenueReport | None: ...
    def cancel(self, client_order_id: str) -> VenueReport | None: ...
    def all_orders(self) -> list[VenueReport]: ...


@dataclass
class Order:
    intent: OrderIntent
    state: OrderState = OrderState.NEW
    filled_qty: float = 0.0
    avg_price: float | None = None
    venue_order_id: str | None = None
    reason: str = ""
    context: dict = field(default_factory=dict)
    booked: bool = False
    updated_at: str = ""

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL

    def to_doc(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_doc(cls, d: Mapping[str, Any]) -> "Order":
        d = dict(d)
        return cls(**{**d, "intent": OrderIntent(**d["intent"]), "state": OrderState(d["state"])})


class PaperOMS:
    def __init__(self, root: Path | str, venue: Venue, *, clock: Callable[[], datetime] | None = None) -> None:
        self.root = Path(root)
        self.venue = venue
        self.path = self.root / "oms_orders.json"
        self.lock = self.root / "oms_orders.lock"
        self.journal = HashChainLog(self.root, "oms_journal", OMSError)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # -- persistence ---------------------------------------------------------------------
    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": OMS_SCHEMA, "halt": None, "orders": {}}
        try:
            doc = read_json_object(self.path)
        except PersistenceError as exc:
            raise OMSError(f"oms_state_unreadable:{exc}") from exc
        if doc.get("schema") != OMS_SCHEMA:
            raise OMSError("oms_schema_mismatch")
        return doc

    def _mutate(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock, timeout_seconds=10.0):
            doc = self._read()
            out = fn(doc)
            atomic_write_json(self.path, doc, expected_root=self.root)
        return out

    def _log(self, event: str, **body: Any) -> None:
        self.journal.append({"event": event, "at_utc": self.clock().isoformat(), **body})

    def get(self, client_order_id: str) -> Order | None:
        d = self._read()["orders"].get(client_order_id)
        return Order.from_doc(d) if d else None

    def orders(self) -> list[Order]:
        return [Order.from_doc(d) for d in self._read()["orders"].values()]

    @property
    def halted(self) -> dict | None:
        return self._read()["halt"]

    def _transition(self, order: Order, report: VenueReport | None, *, state: OrderState | None = None,
                    reason: str = "") -> Order:
        new_state = state or OrderState(report.status)
        if new_state != order.state and new_state not in _ALLOWED.get(order.state, set()):
            raise OMSError(f"illegal_transition:{order.state.value}->{new_state.value}")
        if report is not None:
            if report.filled_qty < order.filled_qty - 1e-12:
                raise OMSError("venue_reported_fill_decrease")
            if report.filled_qty > order.intent.quantity * (1 + 1e-9):
                raise OMSError("venue_overfill")
            order = replace(order, filled_qty=float(report.filled_qty), avg_price=report.avg_price,
                            venue_order_id=report.venue_order_id or order.venue_order_id)
        order = replace(order, state=new_state, reason=reason or (report.reason if report else "") or order.reason,
                        updated_at=self.clock().isoformat())
        self._save(order)
        self._log("ORDER_STATE", client_order_id=order.intent.client_order_id, state=new_state.value,
                  filled_qty=order.filled_qty, avg_price=order.avg_price, reason=order.reason)
        return order

    def _save(self, order: Order) -> None:
        def fn(doc):
            doc["orders"][order.intent.client_order_id] = order.to_doc()
        self._mutate(fn)

    # -- submission ------------------------------------------------------------------------
    def submit(self, intent: OrderIntent, *, context: Mapping[str, Any] | None = None) -> Order:
        intent.check()
        halt = self.halted
        existing = self.get(intent.client_order_id)
        if existing is not None:
            if existing.intent != intent:
                raise OMSError("client_order_id_conflict")
            return existing  # idempotent: never sent twice
        order = Order(intent, context=dict(context or {}), updated_at=self.clock().isoformat())
        if halt:
            order = replace(order, state=OrderState.REJECTED, reason="oms_emergency_halt")
            self._save(order)
            self._log("ORDER_REFUSED", client_order_id=intent.client_order_id, reason="oms_emergency_halt")
            return order
        self._save(order)  # persisted BEFORE contacting the venue: a crash leaves NEW, reconcilable
        self._log("ORDER_NEW", client_order_id=intent.client_order_id, user_id=intent.user_id, symbol=intent.symbol,
                  side=intent.side, quantity=intent.quantity, venue=self.venue.name)
        try:
            report = self.venue.submit(intent)
        except VenueDisconnected:
            return self._transition(order, None, state=OrderState.UNKNOWN, reason="venue_disconnected_on_submit")
        order = self._transition(order, report)
        return self._finish_ioc(order)

    def _finish_ioc(self, order: Order) -> Order:
        """Immediate-or-cancel: any unfilled remainder is cancelled at the venue."""
        if order.state not in {OrderState.ACK, OrderState.PARTIALLY_FILLED}:
            return order
        try:
            report = self.venue.cancel(order.intent.client_order_id)
        except VenueDisconnected:
            return self._transition(order, None, state=OrderState.UNKNOWN, reason="venue_disconnected_on_cancel")
        if report is None:
            return self._transition(order, None, state=OrderState.UNKNOWN, reason="venue_lost_order_on_cancel")
        return self._transition(order, report)

    def mark_booked(self, client_order_id: str) -> None:
        def fn(doc):
            doc["orders"][client_order_id]["booked"] = True
        self._mutate(fn)

    # -- reconciliation ----------------------------------------------------------------------
    def reconcile(self) -> dict[str, Any]:
        """Resolve non-terminal orders from the venue's records and compare everything else."""
        resolved, unresolved, mismatches = [], [], []
        for order in self.orders():
            coid = order.intent.client_order_id
            if order.state == OrderState.REJECTED and order.reason == "oms_emergency_halt":
                continue  # never sent
            try:
                report = self.venue.status(coid)
            except VenueDisconnected:
                if not order.terminal:
                    unresolved.append(coid)
                continue
            if not order.terminal:
                if report is None:
                    if order.state in {OrderState.NEW, OrderState.UNKNOWN}:
                        resolved.append(self._transition(order, None, state=OrderState.REJECTED,
                                                         reason="not_received_by_venue"))
                    else:
                        unresolved.append(coid)
                    continue
                order = self._transition(order, report)
                order = self._finish_ioc(order)
                (resolved if order.terminal else unresolved).append(order if order.terminal else coid)
                continue
            if report is None:
                if order.filled_qty > 0:
                    mismatches.append({"client_order_id": coid, "issue": "filled_order_missing_at_venue"})
            elif abs(report.filled_qty - order.filled_qty) > 1e-9:
                mismatches.append({"client_order_id": coid, "issue": "filled_qty_mismatch",
                                   "oms": order.filled_qty, "venue": report.filled_qty})
        try:
            known = {o.intent.client_order_id for o in self.orders()}
            orphans = [r.client_order_id for r in self.venue.all_orders() if r.client_order_id not in known]
        except VenueDisconnected:
            orphans, unresolved = [], unresolved + ["venue_unreachable"]
        report = {"resolved": [o.intent.client_order_id for o in resolved], "unresolved": unresolved,
                  "mismatches": mismatches, "orphan_venue_orders": orphans,
                  "clean": not (unresolved or mismatches or orphans)}
        self._log("RECONCILIATION", **report)
        report["resolved_orders"] = resolved
        return report

    # -- emergency shutdown ----------------------------------------------------------------
    def emergency_shutdown(self, *, actor_ctx: Mapping[str, Any], reason: str) -> dict[str, Any]:
        actor = str((actor_ctx or {}).get("user_id") or "")
        if not actor:
            raise OMSError("actor_required")
        halt = {"actor": actor, "reason": str(reason)[:200], "at_utc": self.clock().isoformat()}

        def fn(doc):
            doc["halt"] = doc["halt"] or halt
        self._mutate(fn)  # halt first: nothing new can be sent while cancelling
        self._log("EMERGENCY_HALT", **halt)
        cancelled, failed = [], []
        for order in self.orders():
            if order.terminal:
                continue
            coid = order.intent.client_order_id
            try:
                report = self.venue.cancel(coid)
            except VenueDisconnected:
                failed.append(coid)
                continue
            if report is None:
                failed.append(coid)
                continue
            self._transition(order, report)
            cancelled.append(coid)
        out = {"halted": True, "cancelled": cancelled, "cancel_failed": failed}
        self._log("EMERGENCY_CANCEL_SWEEP", **out)
        return out

    def resume(self, *, actor_ctx: Mapping[str, Any]) -> None:
        if str((actor_ctx or {}).get("role", "")).upper() != ADMIN_ROLE or not actor_ctx.get("user_id"):
            raise OMSError("super_user_required")
        rec = self.reconcile()
        if not rec["clean"]:
            raise OMSError("resume_requires_clean_reconciliation")

        def fn(doc):
            doc["halt"] = None
        self._mutate(fn)
        self._log("HALT_CLEARED", actor=str(actor_ctx["user_id"]))


# ---------------------------------------------------------------------------------------------
@dataclass
class VenueBehaviour:
    reject_reason: str = ""
    fill_fraction: float = 1.0
    slippage_bps: float = 0.0
    disconnect: str = ""  # "" | "before_send" | "after_send"


class SimulatedVenue:
    """Deterministic paper venue for verification. Dedupes by client_order_id like real venues.

    Behaviour comes from a FIFO script (one per submit) falling back to `default`. Slippage is
    always adverse to the order side. `down=True` makes every call raise VenueDisconnected.
    """

    name = "SIMULATED_PAPER_VENUE"

    def __init__(self, default: VenueBehaviour | None = None, script: list[VenueBehaviour] | None = None) -> None:
        self.default = default or VenueBehaviour()
        self.script = list(script or [])
        self.book: dict[str, VenueReport] = {}
        self.down = False
        self.submits = 0

    def _check(self) -> None:
        if self.down:
            raise VenueDisconnected("venue_down")

    def submit(self, intent: OrderIntent) -> VenueReport:
        self._check()
        if intent.client_order_id in self.book:
            return self.book[intent.client_order_id]
        b = self.script.pop(0) if self.script else self.default
        self.submits += 1
        if b.disconnect == "before_send":
            raise VenueDisconnected("lost_before_send")
        vid = f"V{len(self.book) + 1:06d}"
        if b.reject_reason:
            rep = VenueReport(intent.client_order_id, vid, "REJECTED", reason=b.reject_reason)
        else:
            qty = intent.quantity * max(0.0, min(1.0, b.fill_fraction))
            sign = 1.0 if intent.side == "BUY" else -1.0
            px = intent.reference_price * (1 + sign * abs(b.slippage_bps) / 10_000.0)
            status = "FILLED" if qty >= intent.quantity else ("PARTIALLY_FILLED" if qty > 0 else "ACK")
            rep = VenueReport(intent.client_order_id, vid, status, qty, px if qty > 0 else None)
        self.book[intent.client_order_id] = rep
        if b.disconnect == "after_send":
            raise VenueDisconnected("lost_after_send")
        return rep

    def status(self, client_order_id: str) -> VenueReport | None:
        self._check()
        return self.book.get(client_order_id)

    def cancel(self, client_order_id: str) -> VenueReport | None:
        self._check()
        rep = self.book.get(client_order_id)
        if rep is None:
            return None
        if rep.status in {"ACK", "PARTIALLY_FILLED"}:
            rep = replace(rep, status="CANCELLED", reason="cancelled_remainder")
            self.book[client_order_id] = rep
        return rep

    def all_orders(self) -> list[VenueReport]:
        self._check()
        return list(self.book.values())
