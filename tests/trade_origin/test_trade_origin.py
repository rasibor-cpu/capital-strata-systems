"""Trade-origin attribution, performance segregation and commercial ledgers (Issue #102, policy TO-2.0.0)."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.trade_origin.commercial import (DRAFT_POLICY, OWNER_STATED_FEE_CONCEPT, CommercialPolicy,
                                                 ledger_entries, statement)
from backend.app.trade_origin.lifecycle import TradeLifecycle
from backend.app.trade_origin.model import (ALLOWED_TRANSITIONS, DEFAULT_POLICY, ORIGIN_LABELS, AttributionError,
                                            InMemoryRecommendationRegistry, MaterialityPolicy, OrderIntent,
                                            OriginLedger, Severity, TradeCard, TradeOrigin, classify_order,
                                            reproduce)
from backend.app.trade_origin.performance import check_totals, from_legacy_closed_trades, segregate

T0 = datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc)
ACT = T0 + timedelta(minutes=3)
LATER = T0 + timedelta(days=1)


@pytest.fixture
def world():
    reg, ledger = InMemoryRecommendationRegistry(), OriginLedger()
    card = TradeCard("REC-1", "ACME", "BUY", 100, "LIMIT", T0, T0 + timedelta(hours=1), limit_price=50.0,
                     entry_low=49.8, entry_high=50.2, max_slippage_bps=40, stop_price=48.0, stop_tolerance_bps=50,
                     target_price=56.0, trade_card_id="CARD-1")
    reg.add(card)
    return reg, ledger, card


def order_from(card, oid="O-1", **changes):
    o = OrderIntent(oid, "user-1", card.symbol, card.side, card.quantity, card.order_type, ACT, card.limit_price,
                    card.stop_price, card.target_price, card.leverage, card.recommendation_id, card.version,
                    card.fingerprint, True)
    return replace(o, **changes)


def user_order(oid, symbol="ACME", side="SELL", qty=1, at=ACT):
    return OrderIntent(oid, "user-1", symbol, side, qty, "MARKET", at)


# ---------------------------------------------------------------- four states, labels
def test_four_states_and_labels():
    assert [o.value for o in TradeOrigin] == ["CSS_RECOMMENDED", "CSS_RECOMMENDED_MODIFIED", "USER_INDEPENDENT",
                                              "ORIGIN_UNDER_REVIEW"]
    assert ORIGIN_LABELS[TradeOrigin.CSS_RECOMMENDED_MODIFIED] == "CSS Recommended — Modified by You"
    assert ORIGIN_LABELS[TradeOrigin.USER_INDEPENDENT] == "Your Own Trade"
    assert TradeOrigin.parse("UNATTRIBUTED_REVIEW_REQUIRED") is TradeOrigin.ORIGIN_UNDER_REVIEW
    assert TradeOrigin.parse("probably_css") is TradeOrigin.ORIGIN_UNDER_REVIEW


# ---------------------------------------------------------------- classification
def test_css_recommended_as_recommended(world):
    reg, _, card = world
    e = classify_order(order_from(card), reg, ACT)
    assert e.origin is TradeOrigin.CSS_RECOMMENDED and e.deviations == ()
    assert e.recommendation_id == "REC-1" and e.recommendation_version == 1 and e.trade_card_id == "CARD-1"
    assert e.recommendation["limit_price"] == 50.0 and e.order["quantity"] == 100
    assert e.policy_version == DEFAULT_POLICY.version and e.policy_fingerprint == DEFAULT_POLICY.fingerprint


def test_user_independent_even_when_identical_to_a_recommendation(world):
    """No fuzzy matching: a lookalike order without the recommendation reference is the user's own trade."""
    reg, _, card = world
    lookalike = order_from(card, oid="O-2", recommendation_id=None, recommendation_version=None, card_fingerprint=None,
                           via_css_workflow=False)
    assert classify_order(lookalike, reg, ACT).origin is TradeOrigin.USER_INDEPENDENT


@pytest.mark.parametrize("change,field_,sev", [
    ({"quantity": 60}, "quantity", Severity.NON_MATERIAL),            # smaller = less exposure
    ({"limit_price": 50.1}, None, None),                               # inside the entry zone
    ({"limit_price": 49.5}, "entry", Severity.NON_MATERIAL),           # better than the zone
    ({"stop_price": 48.5}, "stop_price", Severity.NON_MATERIAL),       # tighter stop
    ({"stop_price": 47.8}, "stop_price", Severity.NON_MATERIAL),       # widened within the card's 50 bps tolerance
])
def test_non_material_changes_stay_css_recommended(world, change, field_, sev):
    reg, _, card = world
    e = classify_order(order_from(card, **change), reg, ACT)
    assert e.origin is TradeOrigin.CSS_RECOMMENDED
    if field_:
        assert [(d.field, d.severity) for d in e.deviations] == [(field_, sev)]


@pytest.mark.parametrize("change,field_", [
    ({"quantity": 101}, "quantity"),                  # any increase under the default allowance (0)
    ({"leverage": 2.0}, "leverage"),
    ({"limit_price": 50.6}, "entry"),                 # worse than the zone
    ({"stop_price": None}, "stop_price"),             # stop removed
    ({"stop_price": 47.0}, "stop_price"),             # widened beyond tolerance
])
def test_material_changes_are_modified(world, change, field_):
    reg, _, card = world
    e = classify_order(order_from(card, **change), reg, ACT)
    assert e.origin is TradeOrigin.CSS_RECOMMENDED_MODIFIED
    assert any(d.field == field_ and d.severity is Severity.MATERIAL for d in e.deviations)


def test_expired_recommendation_is_modified_by_default(world):
    reg, _, card = world
    e = classify_order(order_from(card, action_at=T0 + timedelta(hours=2)), reg, T0 + timedelta(hours=2))
    assert e.origin is TradeOrigin.CSS_RECOMMENDED_MODIFIED and "expired" in e.reason


def test_target_change_waits_for_policy_decision(world):
    reg, _, card = world
    e = classify_order(order_from(card, target_price=60.0), reg, ACT)
    assert e.origin is TradeOrigin.ORIGIN_UNDER_REVIEW
    assert e.deviations[0].severity is Severity.POLICY_PENDING
    decided = MaterialityPolicy(target_change_material=False)
    assert classify_order(order_from(card, target_price=60.0), reg, ACT, decided).origin is TradeOrigin.CSS_RECOMMENDED


@pytest.mark.parametrize("change", [{"side": "SELL"}, {"symbol": "OTHER"}])
def test_thesis_break_goes_to_review_until_policy_decides(world, change):
    reg, _, card = world
    assert classify_order(order_from(card, **change), reg, ACT).origin is TradeOrigin.ORIGIN_UNDER_REVIEW
    pol = MaterialityPolicy(thesis_break_disposition=TradeOrigin.USER_INDEPENDENT)
    assert classify_order(order_from(card, **change), reg, ACT, pol).origin is TradeOrigin.USER_INDEPENDENT


def test_entry_without_zone_uses_fallback_only_when_decided(world):
    reg, _, _ = world
    card = TradeCard("REC-2", "ACME", "BUY", 10, "LIMIT", T0, T0 + timedelta(hours=1), limit_price=50.0)
    reg.add(card)
    o = order_from(card, limit_price=50.1)
    assert classify_order(o, reg, ACT).origin is TradeOrigin.ORIGIN_UNDER_REVIEW
    assert classify_order(o, reg, ACT, MaterialityPolicy(entry_fallback_tolerance_bps=25)).origin is TradeOrigin.CSS_RECOMMENDED
    assert classify_order(o, reg, ACT, MaterialityPolicy(entry_fallback_tolerance_bps=10)).origin is TradeOrigin.CSS_RECOMMENDED_MODIFIED


@pytest.mark.parametrize("change", [
    {"recommendation_id": "REC-MISSING"},             # unknown recommendation
    {"recommendation_version": 2},                     # version not on record
    {"recommendation_version": None},                  # version missing
    {"card_fingerprint": "f" * 64},                    # card changed / tampered
    {"via_css_workflow": False},                       # reference outside the governed workflow
])
def test_unprovable_attribution_goes_to_review(world, change):
    reg, _, card = world
    assert classify_order(order_from(card, **change), reg, ACT).origin is TradeOrigin.ORIGIN_UNDER_REVIEW


def test_policy_pending_list_is_explicit():
    assert set(DEFAULT_POLICY.pending_decisions()) == {"entry_fallback_tolerance_bps", "fill_slippage_fallback_bps",
                                                       "target_change_material", "thesis_break_disposition"}


# ---------------------------------------------------------------- reproducibility and immutability
@pytest.mark.parametrize("change", [{}, {"quantity": 150}, {"stop_price": None}, {"target_price": 60.0},
                                    {"side": "SELL"}, {"quantity": 50, "stop_price": 48.5}])
def test_determination_is_reproducible_from_the_record(world, change):
    reg, _, card = world
    e = classify_order(order_from(card, **change), reg, ACT)
    origin, devs = reproduce(json.loads(json.dumps(e.to_dict())) and e)       # record is JSON-serialisable
    assert origin is e.origin and devs == e.deviations


def test_record_is_immutable_and_never_silently_replaced(world):
    reg, ledger, card = world
    e = ledger.record(classify_order(order_from(card), reg, ACT))
    ledger.record(e)                                                   # identical re-record is fine
    with pytest.raises(AttributionError):
        ledger.record(replace(e, origin=TradeOrigin.USER_INDEPENDENT))
    with pytest.raises(Exception):
        e.origin = TradeOrigin.USER_INDEPENDENT                        # frozen dataclass


def test_registry_versions_are_immutable(world):
    reg, _, card = world
    with pytest.raises(AttributionError):
        reg.add(replace(card, quantity=1))
    reg.add(replace(card, quantity=1, version=2))                      # a new version is fine
    assert reg.get("REC-1", 1).quantity == 100 and reg.get("REC-1", 2).quantity == 1


# ---------------------------------------------------------------- state machine
def test_review_resolution_needs_reviewer_reason_and_evidence(world):
    reg, ledger, card = world
    ledger.record(classify_order(order_from(card, target_price=60.0), reg, ACT))
    with pytest.raises(AttributionError):
        ledger.transition("O-1", TradeOrigin.CSS_RECOMMENDED, LATER, "system:auto", "x", {"a": 1})   # wrong actor
    with pytest.raises(AttributionError):
        ledger.transition("O-1", TradeOrigin.CSS_RECOMMENDED, LATER, "reviewer:r1", "ok")           # no evidence
    with pytest.raises(AttributionError):
        ledger.transition("O-1", TradeOrigin.CSS_RECOMMENDED, LATER, "reviewer:r1", " ", {"a": 1})  # no reason
    t = ledger.transition("O-1", TradeOrigin.CSS_RECOMMENDED_MODIFIED, LATER, "reviewer:r1",
                          "Target change judged material under interim guidance", {"ticket": "REV-7"})
    assert ledger.current("O-1") is TradeOrigin.CSS_RECOMMENDED_MODIFIED and t.from_origin is TradeOrigin.ORIGIN_UNDER_REVIEW
    h = ledger.history("O-1")
    assert [x.get("origin", x.get("to")) for x in h] == ["ORIGIN_UNDER_REVIEW", "CSS_RECOMMENDED_MODIFIED"]
    assert ledger.get("O-1").origin is TradeOrigin.ORIGIN_UNDER_REVIEW         # original record untouched


def test_user_independent_is_terminal(world):
    reg, ledger, _ = world
    ledger.record(classify_order(user_order("U-1", side="BUY"), reg, ACT))
    for to in (TradeOrigin.CSS_RECOMMENDED, TradeOrigin.CSS_RECOMMENDED_MODIFIED, TradeOrigin.ORIGIN_UNDER_REVIEW):
        with pytest.raises(AttributionError):
            ledger.transition("U-1", to, LATER, "reviewer:r1", "try", {"x": 1})
    assert ALLOWED_TRANSITIONS[TradeOrigin.USER_INDEPENDENT] == {}


def test_css_states_cannot_be_promoted_by_system(world):
    reg, ledger, card = world
    ledger.record(classify_order(order_from(card, quantity=150), reg, ACT))
    with pytest.raises(AttributionError):
        ledger.transition("O-1", TradeOrigin.CSS_RECOMMENDED, LATER, "system:x", "upgrade")


@pytest.mark.parametrize("fill,expected", [(50.1, TradeOrigin.CSS_RECOMMENDED),        # inside zone
                                           (50.15, TradeOrigin.CSS_RECOMMENDED),       # inside zone
                                           (50.19, TradeOrigin.CSS_RECOMMENDED),
                                           (50.3, TradeOrigin.CSS_RECOMMENDED_MODIFIED)])  # 60 bps > 40 bps
def test_fill_check(world, fill, expected):
    reg, ledger, card = world
    ledger.record(classify_order(order_from(card), reg, ACT))
    t = ledger.apply_fill_check("O-1", card, fill, ACT)
    assert ledger.current("O-1") is expected
    if t:
        assert t.actor == "system:fill_check" and t.evidence["deviation"]["field"] == "fill_price"


def test_fill_check_with_undecided_slippage_goes_to_review(world):
    reg, ledger, _ = world
    card = TradeCard("REC-3", "ACME", "BUY", 10, "MARKET", T0, T0 + timedelta(hours=1), limit_price=50.0)
    reg.add(card)
    ledger.record(classify_order(order_from(card, oid="O-3"), reg, ACT))
    ledger.apply_fill_check("O-3", card, 50.2, ACT)
    assert ledger.current("O-3") is TradeOrigin.ORIGIN_UNDER_REVIEW


# ---------------------------------------------------------------- lifecycle provenance
def test_recommendation_to_order_to_fill_provenance(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))
    lot = lc.apply_open_fill("O-1", "F-1", "ACME", "BUY", 60, 50.0, ACT)
    lc.apply_open_fill("O-1", "F-2", "ACME", "BUY", 40, 50.5, ACT)
    assert lc.origin_of(lot) is TradeOrigin.CSS_RECOMMENDED and lot.quantity_open == 100
    assert lot.avg_entry_price == pytest.approx(50.2)
    assert all(j["origin"] == "CSS_RECOMMENDED" and j["recommendation_id"] == "REC-1"
               and j["recommendation_version"] == 1 and j["policy_version"] for j in lc.journal)


def test_fill_without_recorded_origin_is_refused(world):
    _, ledger, _ = world
    with pytest.raises(AttributionError):
        TradeLifecycle(ledger).apply_open_fill("NOPE", "F-1", "ACME", "BUY", 1, 1.0, ACT)


def test_partial_and_final_close_keep_lot_origin(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))
    lc.apply_open_fill("O-1", "F-1", "ACME", "BUY", 100, 50.0, ACT)
    ledger.record(classify_order(user_order("C-1", qty=40), reg, ACT))
    ledger.record(classify_order(user_order("C-2", qty=60), reg, ACT))
    j1 = lc.apply_close_fill("C-1", "F-2", 40, 55.0, ACT, lot_id="O-1")
    j2 = lc.apply_close_fill("C-2", "F-3", 60, 49.0, ACT, lot_id="O-1")
    assert j1[0]["event"] == "partial_close" and j2[0]["event"] == "final_close"
    assert j1[0]["origin"] == "CSS_RECOMMENDED" and j1[0]["closing_order_origin"] == "USER_INDEPENDENT"
    assert lc.lots["O-1"].realized_pnl == pytest.approx(40 * 5 - 60 * 1) and lc.lots["O-1"].is_closed


def test_close_across_mixed_origins_requires_a_lot(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))
    ledger.record(classify_order(user_order("U-1", side="BUY", qty=50), reg, ACT))
    lc.apply_open_fill("O-1", "F-1", "ACME", "BUY", 100, 50.0, ACT)
    lc.apply_open_fill("U-1", "F-2", "ACME", "BUY", 50, 51.0, ACT)
    ledger.record(classify_order(user_order("C-1", qty=30), reg, ACT))
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
    ledger.record(classify_order(user_order("C-1", qty=20), reg, ACT))
    with pytest.raises(AttributionError):
        lc.apply_close_fill("C-1", "F-9", 20, 51.0, ACT, lot_id="O-1")


# ---------------------------------------------------------------- performance segregation
def _mixed_book(world):
    reg, ledger, card = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(order_from(card), reg, ACT))                                # CSS
    ledger.record(classify_order(order_from(card, oid="O-M", quantity=200), reg, ACT))        # modified
    ledger.record(classify_order(user_order("U-1", "XYZ", "BUY", 10), reg, ACT))             # user
    ledger.record(classify_order(order_from(card, oid="O-R", target_price=70.0), reg, ACT))   # review
    lc.apply_open_fill("O-1", "F1", "ACME", "BUY", 100, 50.0, ACT)
    lc.apply_open_fill("O-M", "F2", "ACME", "BUY", 200, 50.0, ACT)
    lc.apply_open_fill("U-1", "F3", "XYZ", "BUY", 10, 20.0, ACT)
    lc.apply_open_fill("O-R", "F4", "ACME", "BUY", 10, 50.0, ACT)
    for cid in ("C1", "C2", "C3", "C4"):
        ledger.record(classify_order(user_order(cid, at=LATER), reg, LATER))
    lc.apply_close_fill("C1", "F5", 100, 52.0, LATER, lot_id="O-1")      # CSS +200
    lc.apply_close_fill("C2", "F6", 100, 49.0, LATER, lot_id="O-M")      # modified −100, 100 still open
    lc.apply_close_fill("C3", "F7", 10, 18.0, LATER, lot_id="U-1")       # user −20
    lc.apply_close_fill("C4", "F8", 10, 53.0, LATER, lot_id="O-R")       # review +30
    return lc


def test_performance_segregation_and_views(world):
    lc = _mixed_book(world)
    r = segregate(lc, {"ACME": 51.0})
    segs = {s["origin"]: s for s in r["segments"]}
    assert segs["CSS_RECOMMENDED"]["realized_pnl"] == 200 and segs["CSS_RECOMMENDED"]["wins"] == 1
    assert segs["CSS_RECOMMENDED_MODIFIED"]["realized_pnl"] == -100 and segs["CSS_RECOMMENDED_MODIFIED"]["unrealized_pnl"] == 100
    assert segs["USER_INDEPENDENT"]["realized_pnl"] == -20 and segs["USER_INDEPENDENT"]["losses"] == 1
    assert segs["ORIGIN_UNDER_REVIEW"]["realized_pnl"] == 30
    v = r["views"]
    assert v["css_attributable"]["realized_pnl"] == 100 and v["independent"]["realized_pnl"] == -20
    assert v["under_review"]["realized_pnl"] == 30 and v["combined"]["realized_pnl"] == 110
    assert r["total"]["realized_pnl"] == 110 and check_totals(r) == []


def test_independent_results_never_appear_in_css_views(world):
    reg, ledger, _ = world
    lc = TradeLifecycle(ledger)
    ledger.record(classify_order(user_order("U-1", "XYZ", "BUY", 10), reg, ACT))
    lc.apply_open_fill("U-1", "F1", "XYZ", "BUY", 10, 20.0, ACT)
    ledger.record(classify_order(user_order("C-1", "XYZ"), reg, LATER))
    lc.apply_close_fill("C-1", "F2", 10, 30.0, LATER, lot_id="U-1")       # big independent win
    r = segregate(lc, {})
    assert r["views"]["css_attributable"]["realized_pnl"] == 0 and r["views"]["independent"]["realized_pnl"] == 100
    s = statement(lc)
    assert s["attributable_base"]["realized_pnl"] == 0 and s["ledgers"]["USER_INDEPENDENT"]["realized_pnl"] == 100


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
    assert segs["ORIGIN_UNDER_REVIEW"]["closed_trades"] == 2
    assert segs["USER_INDEPENDENT"]["realized_pnl"] == -2 and segs["CSS_RECOMMENDED"]["closed_trades"] == 0
    assert check_totals(r) == []


def test_tampered_totals_detected(world):
    _, ledger, _ = world
    r = segregate(TradeLifecycle(ledger), {})
    r["total"]["realized_pnl"] = 99
    assert check_totals(r)


# ---------------------------------------------------------------- commercial ledgers
def test_four_separate_ledgers_and_draft_policy_computes_no_fee(world):
    lc = _mixed_book(world)
    s = statement(lc)
    led = {k: v["realized_pnl"] for k, v in s["ledgers"].items()}
    assert led == {"CSS_RECOMMENDED": 200, "CSS_RECOMMENDED_MODIFIED": -100, "USER_INDEPENDENT": -20,
                   "ORIGIN_UNDER_REVIEW": 30}
    assert sum(led.values()) == pytest.approx(segregate(lc, {})["total"]["realized_pnl"])
    assert s["attributable_base"]["included_ledgers"] == ["CSS_RECOMMENDED"] and s["attributable_base"]["realized_pnl"] == 200
    ex = s["attributable_base"]["excluded_ledgers"]
    assert {"USER_INDEPENDENT", "ORIGIN_UNDER_REVIEW", "CSS_RECOMMENDED_MODIFIED"} == set(ex)
    assert "not yet decided" in ex["CSS_RECOMMENDED_MODIFIED"]
    assert s["fee"] is None and s["fee_status"].startswith("NOT_COMPUTED") and "approval" in s["fee_status"]
    assert DRAFT_POLICY.fee_rate is None and OWNER_STATED_FEE_CONCEPT == 0.20     # concept recorded, not applied


def test_resolved_review_moves_into_the_resolved_ledger(world):
    lc = _mixed_book(world)
    lc.ledger.transition("O-R", TradeOrigin.CSS_RECOMMENDED, LATER, "reviewer:r1", "Target change accepted",
                         {"ticket": "REV-1"})
    s = statement(lc)
    assert s["ledgers"]["ORIGIN_UNDER_REVIEW"]["realized_pnl"] == 0
    assert s["ledgers"]["CSS_RECOMMENDED"]["realized_pnl"] == 230


@pytest.mark.parametrize("treatment,base", [("EXCLUDE", 200), ("SEPARATE", 200), ("INCLUDE", 100)])
def test_modified_treatment_is_policy_driven(world, treatment, base):
    s = statement(_mixed_book(world), policy=CommercialPolicy(modified_treatment=treatment))
    assert s["attributable_base"]["realized_pnl"] == base
    assert "USER_INDEPENDENT" not in s["attributable_base"]["included_ledgers"]
    assert "ORIGIN_UNDER_REVIEW" not in s["attributable_base"]["included_ledgers"]


def test_fee_only_under_an_approved_complete_policy_with_loss_recovery(world):
    lc = _mixed_book(world)
    unapproved = CommercialPolicy(fee_rate=0.2, loss_recovery="HIGH_WATER_MARK", modified_treatment="EXCLUDE")
    assert statement(lc, policy=unapproved)["fee"] is None
    approved = replace(unapproved, version="CA-TEST", approved=True, approval_ref="TEST-ONLY")
    s = statement(lc, policy=approved)
    assert s["fee"] == pytest.approx(40.0) and s["fee_status"].startswith("COMPUTED")
    # Prior losses must be recovered first: cumulative 200 - 150 = 50 is below the previous peak of 100 -> no fee.
    s2 = statement(lc, policy=approved, prior_high_water_mark=100.0, prior_cumulative_attributable=-150.0)
    assert s2["loss_recovery"]["chargeable_profit"] == 0 and s2["fee"] == 0
    s3 = statement(lc, policy=approved, prior_high_water_mark=100.0, prior_cumulative_attributable=0.0)
    assert s3["loss_recovery"]["chargeable_profit"] == 100 and s3["fee"] == pytest.approx(20.0)


def test_unsupported_loss_recovery_method_computes_no_fee(world):
    pol = CommercialPolicy(approved=True, approval_ref="X", fee_rate=0.2, loss_recovery="CUSTOM", modified_treatment="EXCLUDE")
    s = statement(_mixed_book(world), policy=pol)
    assert s["fee"] is None and s["loss_recovery"]["status"] == "UNSUPPORTED_METHOD"


def test_statement_period_filter(world):
    lc = _mixed_book(world)
    assert ledger_entries(lc, end=LATER) == []
    assert len(ledger_entries(lc, start=LATER)) == 4
