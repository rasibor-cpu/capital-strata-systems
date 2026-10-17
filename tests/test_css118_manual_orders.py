"""Closeout C3: manual paper orders use CSS's own fresh market assessment; the user keeps authority.

The user decides instrument, side, size and stop. CSS supplies only its assessment (price,
probability, edge, costs) recorded from CSS engine signals, and enforces every platform limit.
The user's size is a cap that CSS may reduce but never enlarge. CSS-Assisted orders need an
explicit per-order approval.
"""
from __future__ import annotations

import time
from datetime import timedelta

import pytest

from css118_support import KEY, NOW, SESSION, activate, mandate_request, signal, system
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from backend.trading_profiles.router import PaperBook, TradingRouter


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def w(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    sess = (SESSION, time.time())
    router = TradingRouter(engine, book=PaperBook(engine.root), role_resolver=lambda u: "TRADER",
                           session_resolver=lambda u: sess, system_provider=lambda: system())
    return engine, router, sess


def _assess(router, now=NOW, **kw):
    """A CSS engine signal enters the router; its market view becomes the assessment."""
    router.on_css_engine_signal(signal(trader_id=AUTONOMOUS_SOURCE_ID, **kw), now=now)


def _order(**kw):
    return {"symbol": "EUR/USD", "asset_class": "FX", "side": "BUY", "notional": 300.0, "stop_distance_pct": 1.5,
            "client_order_id": "c1", **kw}


def test_manual_order_with_fresh_css_assessment_is_governed_and_sized_by_the_user(w):
    engine, router, sess = w
    _assess(router)  # before activation, so sim-1 does not also take the CSS signal itself
    activate(engine.consent, "sim-1", "Simulated Trading", None)
    d = router.submit_manual_order("sim-1", sess, _order(), now=NOW + timedelta(seconds=30))
    assert d.outcome == "SIMULATED" and d.notional == 300.0  # the user's size, not CSS's
    assert d.fill["price"] == pytest.approx(1.08 * (1 + 1 / 10_000))  # CSS reference price, adverse slippage


def test_user_size_is_reduced_by_platform_limits_but_never_enlarged(w):
    engine, router, sess = w
    _assess(router)  # before activation, so sim-1 does not also take the CSS signal itself
    activate(engine.consent, "sim-1", "Simulated Trading", None)
    big = router.submit_manual_order("sim-1", sess, _order(notional=50_000.0, client_order_id="c2"), now=NOW)
    from backend.trading_profiles.router import DEFAULT_PAPER_EQUITY_CAD
    assert big.notional == 0.05 * DEFAULT_PAPER_EQUITY_CAD < 50_000.0  # capital governor: 5% of default equity
    activate(engine.consent, "sim-2", "Simulated Trading", None)  # separate account: AntiBleed cooldown is per follower
    small = router.submit_manual_order("sim-2", sess, _order(notional=120.0, client_order_id="c3"), now=NOW)
    assert small.notional == 120.0


def test_user_supplied_price_cannot_improve_the_fill(w):
    engine, router, sess = w
    _assess(router)  # before activation, so sim-1 does not also take the CSS signal itself
    activate(engine.consent, "sim-1", "Simulated Trading", None)
    d = router.submit_manual_order("sim-1", sess, _order(reference_price=0.5, probability=0.99), now=NOW)
    assert d.fill["price"] == pytest.approx(1.08 * (1 + 1 / 10_000))


@pytest.mark.parametrize("case", ["none", "stale", "future", "opposite_side", "other_asset"])
def test_missing_or_unusable_assessment_rejects(w, case):
    engine, router, sess = w
    activate(engine.consent, "sim-1", "Simulated Trading", None)
    when = NOW
    order = _order()
    if case != "none":
        _assess(router, now=NOW)
    if case == "stale":
        when = NOW + timedelta(minutes=6)
    elif case == "future":
        when = NOW - timedelta(minutes=1)
    elif case == "opposite_side":
        order = _order(side="SELL")
    elif case == "other_asset":
        order = _order(asset_class="CRYPTO")
    d = router.submit_manual_order("sim-1", sess, order, now=when)
    assert (d.outcome, d.stage, d.reason) == ("REJECTED", "routing", "manual_order_requires_css_market_assessment")


def test_unreadable_assessment_store_fails_closed(w):
    engine, router, sess = w
    _assess(router)  # before activation, so sim-1 does not also take the CSS signal itself
    activate(engine.consent, "sim-1", "Simulated Trading", None)
    router.assessments.path.write_text("{corrupt", encoding="utf-8")
    d = router.submit_manual_order("sim-1", sess, _order(), now=NOW)
    assert d.reason == "manual_order_requires_css_market_assessment"


@pytest.mark.parametrize("bad", [{"notional": 0}, {"notional": -5}, {"notional": float("nan")}, {"notional": "abc"},
                                 {"stop_distance_pct": 0}, {"notional": None}])
def test_manual_order_requires_explicit_valid_size_and_stop(w, bad):
    engine, router, sess = w
    _assess(router)  # before activation, so sim-1 does not also take the CSS signal itself
    activate(engine.consent, "sim-1", "Simulated Trading", None)
    d = router.submit_manual_order("sim-1", sess, _order(**bad), now=NOW)
    assert (d.stage, d.reason) == ("routing", "manual_order_requires_notional_and_stop")


def test_assisted_manual_order_needs_per_order_approval_at_the_users_size(w):
    engine, router, sess = w
    activate(engine.consent, "assist-1", "CSS-Assisted Trading", "Balanced")
    _assess(router)  # assist-1 also receives this CSS signal as its own proposal
    d = router.submit_manual_order("assist-1", sess, _order(notional=250.0), now=NOW)
    assert d.outcome == "PROPOSED" and d.notional == 250.0
    assert all(p.signal_id != d.signal_id for p in router.book.positions())  # nothing opened before approval
    done = router.decide_proposal("assist-1", sess, d.proposal_id, approve=True, now=NOW)
    assert done.outcome == "COPIED" and done.notional == 250.0


@pytest.mark.parametrize("mode,reason", [("CSS Autonomous Trading", "autonomous_mode_accepts_css_engine_signals_only"),
                                         ("Copy a CSS Trader", "copy_mode_requires_trader_signal")])
def test_manual_orders_refused_in_delegated_modes(w, mode, reason):
    engine, router, sess = w
    if mode == "Copy a CSS Trader":
        activate(engine.consent, "u1", mode, "Balanced", mandate=mandate_request(asset_classes=["FX"]))
    else:
        activate(engine.consent, "u1", mode, "Balanced")
    _assess(router)
    d = router.submit_manual_order("u1", sess, _order(), now=NOW)
    assert (d.stage, d.reason) == ("authority", reason)


def test_manual_order_without_acceptance_is_refused(w):
    _, router, sess = w
    _assess(router)
    d = router.submit_manual_order("nobody", sess, _order(), now=NOW)
    assert (d.stage, d.reason) == ("consent", "consent_missing")


def test_manual_order_cannot_bypass_antibleed_minimum(w):
    engine, router, sess = w
    _assess(router)  # before activation, so sim-1 does not also take the CSS signal itself
    activate(engine.consent, "sim-1", "Simulated Trading", None)
    d = router.submit_manual_order("sim-1", sess, _order(notional=20.0), now=NOW)
    assert d.outcome == "REJECTED" and d.reason == "anti_bleed_guard:trade_size_too_small"
