"""Trade-origin attribution and performance segregation (Issue #102)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.trade_origin.lifecycle import TradeLifecycle
from backend.app.trade_origin.model import (AttributionError, InMemoryRecommendationRegistry, OrderIntent,
                                            OriginLedger, TradeCard, TradeOrigin, classify_order)
from backend.app.trade_origin.performance import check_totals, from_legacy_closed_trades, segregate

T0 = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
ACT = T0 + timedelta(minutes=3)


@pytest.fixture
def world():
    reg, ledger = InMemoryRecommendationRegistry(), OriginLedger()
    card = TradeCard("REC-1", "ACME", "BUY", 100, "LIMIT", T0, T0 + timedelta(hours=1), limit_price=50.0,
                     stop_price=48.0, target_price=56.0, trade_card_id="CARD-1")
    reg.add(card)
    return reg, ledger, card


def order_from(card, oid="O-1", **changes):
    o = OrderIntent(oid, card.symbol, card.side, card.quantity, card.order_type, ACT, card.limit_price,
                    card.stop_price, card.target_price, card.recommendation_id, card.fingerprint, True)
    return replace(o, **changes)


# ---------------------------------------------------------------- classification
def test_css_recommended(world):
    reg, _, card = world
    e = classify_order(order_from(card), reg, ACT)
    assert e.origin is TradeOrigin.CSS_RECOMMENDED and e.recommendation_id == "REC-1"
    assert e.trade_card_id == "CARD-1" and e.card_fingerprint == card.fingerprint and e.policy_version


def test_user_independent_even_when_identical_to_a_recommendation(world):
    reg, _, card = world
    lookalike = order_from(card, oid="O-2", recommendation_id=None, card_fingerprint=None, via_css_workflow=False)
    assert classify_order(lookalike, reg, ACT).origin is TradeOrigin.USER_INDEPENDENT


@pytest.mark.parametrize("change,needle", [({"quantity": 150}, "quantity"), ({"limit_price": 50.5}, "limit_price"),
                                            ({"stop_price": None}, "stop_price removed"),
                                            ({"target_price": 60.0}, "target_price"),
                                            ({"order_type": "MARKET"}, "order_type")])
def test_modified_recommendation(world, change, needle):
    reg, _, card = world
    e = classify_order(order_from(card, **change), reg, ACT)
    assert e.origin is TradeOrigin.CSS_RECOMMENDED_MODIFIED
    assert any(needle in d for d in e.deviations)


def test_small_changes_within_tolerance_stay_recommended(world):
    reg, _, card = world
    e = classify_order(order_from(card, quantity=100.5, limit_price=50.05), reg, ACT)
    assert e.origin is TradeOrigin.CSS_RECOMMENDED


@pytest.mark.parametrize("change", [
    {"recommendation_id": "REC-MISSING"},                       # unknown recommendation
    {"card_fingerprint": "f" * 64},                              # card changed / tampered
    {"via_css_workflow": False},                                 # reference outside the governed workflow
    {"action_at": T0 + timedelta(hours=2)},                      # expired
    {"symbol": "OTHER"},                                         # different instrument
    {"side": "SELL"},                                            # opposite direction
])
def test_ambiguous_attribution_fails_safe(world, change):
    reg, _, card = world
    assert classify_order(order_from(card, **change), reg, ACT).origin is TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED


def test_origin_is_immutable(world):
    reg, ledger, card = world
    e = ledger.record(classify_order(order_from(card), reg, ACT))
    ledger.record(e)                                             # identical re-record is fine
    with pytest.raises(AttributionError):
        ledger.record(replace(e, origin=TradeOrigin.USER_INDEPENDENT))
    with pytest.raises(Exception):
        e.origin = TradeOrigin.USER_INDEPENDENT                  # frozen dataclass


def test_registry_ids_are_immutable(world):
    reg, _, card = world
    with pytest.raises(AttributionError):
        reg.add(replace(card, quantity=1))


# ---------------------------------------------------------------- lifecycle provenance
def test_recommendation_to_order_to_fill_provenance(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))
    lot = lc.apply_open_fill("O-1", "F-1", "ACME", "BUY", 60, 50.0, ACT)
    lc.apply_open_fill("O-1", "F-2", "ACME", "BUY", 40, 50.5, ACT)
    assert lot.origin.origin is TradeOrigin.CSS_RECOMMENDED and lot.quantity_open == 100
    assert lot.avg_entry_price == pytest.approx(50.2)
    assert all(j["origin"] == "CSS_RECOMMENDED" and j["recommendation_id"] == "REC-1" for j in lc.journal)


def test_fill_without_recorded_origin_is_refused(world):
    _, ledger, _ = world
    with pytest.raises(AttributionError):
        TradeLifecycle(ledger).apply_open_fill("NOPE", "F-1", "ACME", "BUY", 1, 1.0, ACT)


def test_partial_and_final_close_keep_lot_origin(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))
    lc.apply_open_fill("O-1", "F-1", "ACME", "BUY", 100, 50.0, ACT)
    # The closing order itself is a manual user order; P&L still belongs to the CSS lot it closes.
    ledger.record(classify_order(OrderIntent("C-1", "ACME", "SELL", 40, "MARKET", ACT), reg, ACT))
    ledger.record(classify_order(OrderIntent("C-2", "ACME", "SELL", 60, "MARKET", ACT), reg, ACT))
    j1 = lc.apply_close_fill("C-1", "F-2", 40, 55.0, ACT, lot_id="O-1")
    j2 = lc.apply_close_fill("C-2", "F-3", 60, 49.0, ACT, lot_id="O-1")
    assert j1[0]["event"] == "partial_close" and j2[0]["event"] == "final_close"
    assert j1[0]["origin"] == "CSS_RECOMMENDED" and j1[0]["closing_order_origin"] == "USER_INDEPENDENT"
    assert lc.lots["O-1"].realized_pnl == pytest.approx(40 * 5 - 60 * 1)
    assert lc.lots["O-1"].is_closed


def test_close_across_mixed_origins_requires_a_lot(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))
    ledger.record(classify_order(OrderIntent("U-1", "ACME", "BUY", 50, "MARKET", ACT), reg, ACT))
    lc.apply_open_fill("O-1", "F-1", "ACME", "BUY", 100, 50.0, ACT)
    lc.apply_open_fill("U-1", "F-2", "ACME", "BUY", 50, 51.0, ACT)
    ledger.record(classify_order(OrderIntent("C-1", "ACME", "SELL", 30, "MARKET", ACT), reg, ACT))
    with pytest.raises(AttributionError):
        lc.apply_close_fill("C-1", "F-3", 30, 52.0, ACT, symbol="ACME")      # would have to guess
    lc.apply_close_fill("C-1", "F-3", 30, 52.0, ACT, lot_id="U-1")           # explicit lot is fine
    assert lc.lots["U-1"].quantity_open == 20 and lc.lots["O-1"].quantity_open == 100


def test_over_close_and_duplicate_fill_refused(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))
    lc.apply_open_fill("O-1", "F-1", "ACME", "BUY", 10, 50.0, ACT)
    with pytest.raises(AttributionError):
        lc.apply_open_fill("O-1", "F-1", "ACME", "BUY", 10, 50.0, ACT)
    ledger.record(classify_order(OrderIntent("C-1", "ACME", "SELL", 20, "MARKET", ACT), reg, ACT))
    with pytest.raises(AttributionError):
        lc.apply_close_fill("C-1", "F-9", 20, 51.0, ACT, lot_id="O-1")


# ---------------------------------------------------------------- performance segregation
def test_performance_segregation(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))                              # CSS
    ledger.record(classify_order(order_from(card, oid="O-M", quantity=200), reg, ACT))      # CSS modified
    ledger.record(classify_order(OrderIntent("U-1", "XYZ", "BUY", 10, "MARKET", ACT), reg, ACT))   # user
    ledger.record(classify_order(order_from(card, oid="O-R", recommendation_id="REC-GONE"), reg, ACT))  # review
    lc.apply_open_fill("O-1", "F1", "ACME", "BUY", 100, 50.0, ACT)
    lc.apply_open_fill("O-M", "F2", "ACME", "BUY", 200, 50.0, ACT)
    lc.apply_open_fill("U-1", "F3", "XYZ", "BUY", 10, 20.0, ACT)
    lc.apply_open_fill("O-R", "F4", "ACME", "BUY", 10, 50.0, ACT)
    for cid in ("C1", "C2", "C3"):
        ledger.record(classify_order(OrderIntent(cid, "ACME", "SELL", 1, "MARKET", ACT), reg, ACT))
    lc.apply_close_fill("C1", "F5", 100, 52.0, ACT, lot_id="O-1")       # CSS +200
    lc.apply_close_fill("C2", "F6", 100, 49.0, ACT, lot_id="O-M")       # modified −100, 100 still open
    lc.apply_close_fill("C3", "F7", 10, 18.0, ACT, lot_id="U-1")        # user −20
    r = segregate(lc, {"ACME": 51.0})
    segs = {s["origin"]: s for s in r["segments"]}
    assert segs["CSS_RECOMMENDED"]["realized_pnl"] == 200 and segs["CSS_RECOMMENDED"]["wins"] == 1
    assert segs["CSS_RECOMMENDED_MODIFIED"]["realized_pnl"] == -100
    assert segs["CSS_RECOMMENDED_MODIFIED"]["unrealized_pnl"] == 100 and segs["CSS_RECOMMENDED_MODIFIED"]["open_positions"] == 1
    assert segs["USER_INDEPENDENT"]["realized_pnl"] == -20 and segs["USER_INDEPENDENT"]["losses"] == 1
    assert segs["UNATTRIBUTED_REVIEW_REQUIRED"]["unrealized_pnl"] == 10
    assert r["headline"]["css_recommended_realized_pnl"] == 200
    assert r["headline"]["user_independent_realized_pnl"] == -20
    assert r["total"]["realized_pnl"] == 80 and check_totals(r) == []
    assert "not calculated here" in r["commercial_note"]


def test_missing_mark_is_reported_not_assumed(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))
    lc.apply_open_fill("O-1", "F1", "ACME", "BUY", 10, 50.0, ACT)
    r = segregate(lc, {})
    assert r["unrealized_incomplete_for"] == ["ACME"] and r["total"]["unrealized_pnl"] == 0


def test_legacy_records_without_origin_are_held_for_review():
    r = from_legacy_closed_trades([{"realized_pnl_usd": 5}, {"realized_pnl_usd": -2, "origin": "USER_INDEPENDENT"},
                                   {"realized_pnl_usd": 1, "origin": "probably_css"}])
    segs = {s["origin"]: s for s in r["segments"]}
    assert segs["UNATTRIBUTED_REVIEW_REQUIRED"]["closed_trades"] == 2
    assert segs["USER_INDEPENDENT"]["realized_pnl"] == -2 and segs["CSS_RECOMMENDED"]["closed_trades"] == 0
    assert check_totals(r) == []


def test_tampered_totals_detected(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    r = segregate(lc, {})
    r["total"]["realized_pnl"] = 99
    assert check_totals(r)
