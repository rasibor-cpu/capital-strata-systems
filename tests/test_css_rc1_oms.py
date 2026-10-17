"""RC1 R2 paper OMS: idempotency, rejection, partial fills, slippage, disconnects, reconciliation,
emergency shutdown, and booking only what the (simulated paper) venue actually filled."""
from __future__ import annotations

import time

import pytest

from css118_support import ADMIN_A, KEY, NOW, SESSION, activate, signal, system
from backend.oms.paper_oms import (
    OMSError,
    OrderIntent,
    OrderState,
    PaperOMS,
    SimulatedVenue,
    VenueBehaviour,
    VenueReport,
)
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from backend.trading_profiles.router import PaperBook, TradingRouter

OPERATOR = {"user_id": "synthetic-operator", "role": "TRADER"}


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def _intent(coid="c-1", qty=10.0, side="BUY", px=100.0):
    return OrderIntent(coid, "u-1", "EUR/USD", side, qty, px)


def _oms(tmp_path, *script, default=None):
    venue = SimulatedVenue(default=default, script=list(script))
    return PaperOMS(tmp_path / "oms", venue), venue


# ------------------------------------------------------------------ OMS unit behaviour
def test_full_fill_applies_adverse_slippage(tmp_path):
    oms, _ = _oms(tmp_path, VenueBehaviour(slippage_bps=10))
    buy = oms.submit(_intent("b"))
    sell = oms.submit(_intent("s", side="SELL"))
    assert buy.state == OrderState.FILLED and buy.avg_price == pytest.approx(100.10)
    assert sell.state == OrderState.FILLED and sell.avg_price == pytest.approx(100.0)  # default: no slippage
    oms2, _ = _oms(tmp_path / "x", VenueBehaviour(slippage_bps=10))
    assert oms2.submit(_intent("s2", side="SELL")).avg_price == pytest.approx(99.90)


def test_duplicate_client_order_id_is_idempotent_and_conflict_refused(tmp_path):
    oms, venue = _oms(tmp_path)
    first = oms.submit(_intent())
    again = oms.submit(_intent())
    assert again == first and venue.submits == 1
    with pytest.raises(OMSError, match="client_order_id_conflict"):
        oms.submit(_intent(qty=11.0))


def test_rejection_books_nothing(tmp_path):
    oms, _ = _oms(tmp_path, VenueBehaviour(reject_reason="insufficient_margin"))
    o = oms.submit(_intent())
    assert o.state == OrderState.REJECTED and o.filled_qty == 0 and o.reason == "insufficient_margin"


def test_partial_fill_remainder_cancelled(tmp_path):
    oms, _ = _oms(tmp_path, VenueBehaviour(fill_fraction=0.4))
    o = oms.submit(_intent())
    assert o.state == OrderState.CANCELLED and o.filled_qty == pytest.approx(4.0) and o.avg_price == 100.0


def test_zero_fill_ack_is_cancelled(tmp_path):
    oms, _ = _oms(tmp_path, VenueBehaviour(fill_fraction=0.0))
    o = oms.submit(_intent())
    assert o.state == OrderState.CANCELLED and o.filled_qty == 0


def test_disconnect_after_send_is_unknown_then_reconciled_to_fill(tmp_path):
    oms, _ = _oms(tmp_path, VenueBehaviour(disconnect="after_send", slippage_bps=5))
    o = oms.submit(_intent())
    assert o.state == OrderState.UNKNOWN and o.filled_qty == 0  # never assumed either way
    rep = oms.reconcile()
    assert rep["resolved"] == ["c-1"] and rep["clean"]
    assert oms.get("c-1").state == OrderState.FILLED and oms.get("c-1").avg_price == pytest.approx(100.05)


def test_disconnect_before_send_reconciles_to_rejected(tmp_path):
    oms, _ = _oms(tmp_path, VenueBehaviour(disconnect="before_send"))
    assert oms.submit(_intent()).state == OrderState.UNKNOWN
    oms.reconcile()
    o = oms.get("c-1")
    assert o.state == OrderState.REJECTED and o.reason == "not_received_by_venue"


def test_venue_down_leaves_order_unresolved(tmp_path):
    oms, venue = _oms(tmp_path, VenueBehaviour(disconnect="after_send"))
    oms.submit(_intent())
    venue.down = True
    rep = oms.reconcile()
    assert "c-1" in rep["unresolved"] and rep["clean"] is False


def test_reconcile_reports_orphans_and_quantity_mismatch(tmp_path):
    oms, venue = _oms(tmp_path)
    oms.submit(_intent())
    venue.book["c-1"] = VenueReport("c-1", "V1", "FILLED", 7.0, 100.0)  # venue disagrees
    venue.book["ghost"] = VenueReport("ghost", "V9", "FILLED", 1.0, 100.0)  # unknown to the OMS
    rep = oms.reconcile()
    assert rep["orphan_venue_orders"] == ["ghost"] and rep["mismatches"][0]["issue"] == "filled_qty_mismatch"
    assert rep["clean"] is False


def test_overfill_and_illegal_transition_are_refused(tmp_path):
    oms, venue = _oms(tmp_path, VenueBehaviour(disconnect="after_send"))
    oms.submit(_intent())
    venue.book["c-1"] = VenueReport("c-1", "V1", "FILLED", 12.0, 100.0)
    with pytest.raises(OMSError, match="venue_overfill"):
        oms.reconcile()
    oms2, _ = _oms(tmp_path / "b")
    filled = oms2.submit(_intent())
    with pytest.raises(OMSError, match="illegal_transition:FILLED->ACK"):
        oms2._transition(filled, VenueReport("c-1", "V1", "ACK"))


def test_emergency_shutdown_cancels_open_orders_blocks_new_and_persists(tmp_path):
    oms, venue = _oms(tmp_path, VenueBehaviour(disconnect="after_send", fill_fraction=0.0))
    oms.submit(_intent())  # venue holds an open ACK order; OMS sees UNKNOWN
    out = oms.emergency_shutdown(actor_ctx=OPERATOR, reason="synthetic drill")
    assert out == {"halted": True, "cancelled": ["c-1"], "cancel_failed": []}
    assert oms.get("c-1").state == OrderState.CANCELLED
    restarted = PaperOMS(tmp_path / "oms", venue)
    assert restarted.halted["actor"] == "synthetic-operator"
    refused = restarted.submit(_intent("c-2"))
    assert refused.state == OrderState.REJECTED and refused.reason == "oms_emergency_halt" and venue.submits == 1
    with pytest.raises(OMSError, match="super_user_required"):
        restarted.resume(actor_ctx=OPERATOR)
    restarted.resume(actor_ctx=ADMIN_A)
    assert restarted.halted is None and restarted.submit(_intent("c-3")).state == OrderState.FILLED


def test_shutdown_with_venue_down_still_halts_and_resume_needs_clean_reconciliation(tmp_path):
    oms, venue = _oms(tmp_path, VenueBehaviour(disconnect="after_send", fill_fraction=0.0))
    oms.submit(_intent())
    venue.down = True
    out = oms.emergency_shutdown(actor_ctx=OPERATOR, reason="venue outage")
    assert out["cancel_failed"] == ["c-1"] and oms.halted
    with pytest.raises(OMSError, match="resume_requires_clean_reconciliation"):
        oms.resume(actor_ctx=ADMIN_A)
    venue.down = False
    oms.resume(actor_ctx=ADMIN_A)  # reconcile cancels the remainder (IOC) -> clean
    assert oms.get("c-1").state == OrderState.CANCELLED and oms.halted is None


def test_journal_is_hash_chained_and_complete(tmp_path):
    oms, _ = _oms(tmp_path, VenueBehaviour(fill_fraction=0.5))
    oms.submit(_intent())
    events = [e["event"] for e in oms.journal.events()]
    assert events[0] == "ORDER_NEW" and events.count("ORDER_STATE") == 2  # PARTIALLY_FILLED, CANCELLED


# ------------------------------------------------------------------ router integration
class World:
    def __init__(self, tmp_path, *script, default=None):
        self.root = tmp_path / "tp"
        self.engine = CopyTradeEngine(self.root, key_provider=lambda: KEY)
        self.venue = SimulatedVenue(default=default, script=list(script))
        self.oms = PaperOMS(self.root / "oms", self.venue)
        self.book = PaperBook(self.root)
        sess = (SESSION, time.time())
        self.router = TradingRouter(self.engine, book=self.book, role_resolver=lambda u: "TRADER",
                                    session_resolver=lambda u: sess, system_provider=lambda: system(), oms=self.oms)
        activate(self.engine.consent, "auto-1", "CSS Autonomous Trading", "Balanced")

    def route(self, sid="sig-1"):
        (d,) = self.router.on_css_engine_signal(signal(signal_id=sid, trader_id=AUTONOMOUS_SOURCE_ID), now=NOW).decisions
        return d

    def executions(self):
        return [r for r in self.engine.ledger.records() if r["record_type"] == "ORDER_EXECUTION"]


def test_router_books_venue_fill_price_not_model_price(tmp_path):
    w = World(tmp_path, VenueBehaviour(slippage_bps=20))
    d = w.route()
    assert d.outcome == "COPIED"
    (pos,) = w.book.positions()
    qty = d.notional / d.fill["price"]
    assert pos.entry_price == pytest.approx(d.fill["price"] * 1.002)
    assert pos.notional == pytest.approx(round(qty * pos.entry_price, 2))
    assert w.executions()[0]["state"] == "FILLED"


def test_router_venue_rejection_opens_no_position(tmp_path):
    w = World(tmp_path, VenueBehaviour(reject_reason="instrument_halted"))
    assert w.route().outcome == "COPIED"  # authorised by the gates ...
    assert w.book.positions() == []  # ... but the venue refused: nothing booked
    assert w.executions()[0]["state"] == "REJECTED" and w.executions()[0]["reason"] == "instrument_halted"


def test_router_partial_fill_books_only_filled_part(tmp_path):
    w = World(tmp_path, VenueBehaviour(fill_fraction=0.25))
    d = w.route()
    (pos,) = w.book.positions()
    assert pos.notional == pytest.approx(d.notional * 0.25, abs=0.02)


def test_router_disconnect_books_after_reconciliation_exactly_once(tmp_path):
    w = World(tmp_path, VenueBehaviour(disconnect="after_send"))
    w.route()
    assert w.book.positions() == []
    rep = w.router.reconcile_orders(now=NOW)
    assert len(rep["booked"]) == 1 and len(w.book.positions()) == 1
    assert w.router.reconcile_orders(now=NOW)["booked"] == [] and len(w.book.positions()) == 1


def test_router_books_fill_left_unbooked_by_a_crash(tmp_path):
    w = World(tmp_path)
    w.router._book_order = lambda order, now: False  # simulate crash between fill and booking
    w.route()
    assert w.book.positions() == []
    del w.router._book_order
    assert len(w.router.reconcile_orders(now=NOW)["booked"]) == 1 and len(w.book.positions()) == 1


def test_router_halt_rejects_before_evaluation(tmp_path):
    w = World(tmp_path)
    w.oms.emergency_shutdown(actor_ctx=OPERATOR, reason="synthetic drill")
    d = w.route()
    assert d.outcome == "REJECTED" and d.reason == "oms_emergency_halt" and w.venue.submits == 0


def test_router_without_oms_is_unchanged(tmp_path):
    w = World(tmp_path)
    w.router.oms = None
    d = w.route()
    (pos,) = w.book.positions()
    assert pos.entry_price == d.fill["price"] and w.executions() == []
