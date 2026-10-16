"""Issue #118 P4: canonical paper routing for CSS-Assisted, Copy a CSS Trader and CSS Autonomous.

Every path ends in CopyTradeEngine (consent -> authority -> personality -> sizing and capital
governors -> trade quality / CAIE -> R14F -> R7 -> ExecutionGate -> paper validation). Context
(role, sign-on session, safety flags) is resolved server-side and fails closed.
"""
from __future__ import annotations

import time
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from css118_support import (
    ADMIN_A,
    KEY,
    NOW,
    SAFE_FLAGS,
    SESSION,
    TRADER,
    activate,
    approve_trader,
    mandate_request,
    public_key_b64,
    signal,
    system,
    trader_key,
)
from backend.trading_profiles.api import PREFIX, create_trading_profiles_router
from backend.trading_profiles.attribution import reconcile
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine, ProposalError
from backend.trading_profiles.router import PaperBook, TradingRouter
from backend.trading_profiles.service import TradingProfileService
from backend.trading_profiles.signal_feed import sign_signal

ROLES = {"copy-1": "TRADER", "copy-2": "TRADER", "auto-1": "TRADER", "assist-1": "TRADER", "sim-1": "TRADER",
         "other-copy": "TRADER", "admin-a": "SUPER_USER", "admin-b": "SUPER_USER"}
ASSESSMENT = {k: v for k, v in asdict(signal()).items()
              if k not in {"signal_id", "trader_id", "symbol", "asset_class", "side", "stop_distance_pct"}}


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


class World:
    def __init__(self, tmp_path, *, pilot=False):
        self.root = tmp_path / "tp"
        self.engine = CopyTradeEngine(self.root, key_provider=lambda: KEY)
        self.sessions = {uid: (SESSION, time.time()) for uid in ROLES}
        self.system = system()
        self.assessment = None
        self.book = PaperBook(self.root, pilot_envelope=pilot)
        self.router = TradingRouter(
            self.engine, book=self.book, role_resolver=ROLES.get, session_resolver=self.sessions.get,
            system_provider=lambda: self._system(), assessment_provider=lambda *a: self.assessment)

    def _system(self):
        if isinstance(self.system, Exception):
            raise self.system
        return self.system

    def copy_user(self, uid, trader=TRADER):
        approve_trader(self.engine.trader_registry, trader)
        activate(self.engine.consent, uid, "Copy a CSS Trader", "Balanced",
                 mandate=mandate_request(trader_id=trader, asset_classes=["FX"]))

    def user(self, uid, mode, personality="Balanced"):
        activate(self.engine.consent, uid, mode, personality)


def _envelope(**overrides):
    payload = {**asdict(signal()), "issued_at_utc": NOW.isoformat(), **overrides}
    return sign_signal(trader_key(payload["trader_id"]), payload)


def _engine_signal(**kw):
    return signal(trader_id=AUTONOMOUS_SOURCE_ID, **kw)


# ------------------------------------------------------------------ copy trading
def test_signed_trader_signal_fans_out_only_to_that_traders_followers(tmp_path):
    w = World(tmp_path)
    w.copy_user("copy-1")
    w.copy_user("copy-2")
    w.copy_user("other-copy", trader="trader-beta")
    w.user("auto-1", "CSS Autonomous Trading")
    result = w.router.on_trader_signal(_envelope(), now=NOW)
    assert result.accepted
    assert sorted((d.follower_user_id, d.outcome) for d in result.decisions) == [("copy-1", "COPIED"), ("copy-2", "COPIED")]
    assert {d.pipeline_status for d in result.decisions} == {"validated_not_executed"}
    assert sorted(p.follower_user_id for p in w.book.positions()) == ["copy-1", "copy-2"]
    assert reconcile(w.engine.ledger.records())["ok"]


def test_unsigned_or_forged_trader_signal_reaches_nobody(tmp_path):
    w = World(tmp_path)
    w.copy_user("copy-1")
    forged = _envelope()
    forged["payload"]["reference_price"] = 2.0
    result = w.router.on_trader_signal(forged, now=NOW)
    assert (result.accepted, result.reason, result.decisions) == (False, "signature_invalid", ())
    assert w.book.positions() == []


def test_suspended_trader_signal_rejected_at_feed(tmp_path):
    w = World(tmp_path)
    w.copy_user("copy-1")
    w.engine.trader_registry.suspend(TRADER, actor_ctx=ADMIN_A, reason="incident", now=NOW)
    result = w.router.on_trader_signal(_envelope(), now=NOW)
    assert not result.accepted and result.reason == "trader_not_authorized:trader_not_active:SUSPENDED"


def test_paused_copy_follower_is_rejected_and_recorded(tmp_path):
    w = World(tmp_path)
    w.copy_user("copy-1")
    w.engine.preferences.pause("copy-1")
    (d,) = w.router.on_trader_signal(_envelope(), now=NOW).decisions
    assert (d.outcome, d.reason) == ("REJECTED", "trading_paused_by_user")


# ------------------------------------------------------------------ CSS engine signals
def test_css_engine_signal_routes_by_mode(tmp_path):
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading")
    w.user("assist-1", "CSS-Assisted Trading")
    w.user("sim-1", "Simulated Trading", None)
    w.copy_user("copy-1")
    result = w.router.on_css_engine_signal(_engine_signal(), now=NOW)
    outcomes = {d.follower_user_id: d.outcome for d in result.decisions}
    assert outcomes == {"auto-1": "COPIED", "assist-1": "PROPOSED", "sim-1": "SIMULATED"}  # copy follower excluded
    assert {p.follower_user_id for p in w.book.positions()} == {"auto-1", "sim-1"}


def test_trader_signal_cannot_be_injected_as_css_engine_signal(tmp_path):
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading")
    result = w.router.on_css_engine_signal(signal(), now=NOW)
    assert (result.accepted, result.reason) == (False, "not_a_css_engine_signal")


def test_assisted_proposal_needs_individual_approval(tmp_path):
    w = World(tmp_path)
    w.user("assist-1", "CSS-Assisted Trading")
    (proposed,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
    assert w.book.positions() == [] and len(w.engine.pending_proposals("assist-1", now=NOW)) == 1
    d = w.router.decide_proposal("assist-1", w.sessions["assist-1"], proposed.proposal_id, approve=True, now=NOW)
    assert d.outcome == "COPIED" and [p.follower_user_id for p in w.book.positions()] == ["assist-1"]
    with pytest.raises(ProposalError, match="proposal_already_decided"):
        w.router.decide_proposal("assist-1", w.sessions["assist-1"], proposed.proposal_id, approve=True, now=NOW)


def test_assisted_rejection_opens_nothing(tmp_path):
    w = World(tmp_path)
    w.user("assist-1", "CSS-Assisted Trading")
    (proposed,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
    d = w.router.decide_proposal("assist-1", w.sessions["assist-1"], proposed.proposal_id, approve=False, now=NOW)
    assert d.outcome == "REJECTED" and w.book.positions() == []


def test_other_user_cannot_decide_a_proposal(tmp_path):
    w = World(tmp_path)
    w.user("assist-1", "CSS-Assisted Trading")
    w.user("auto-1", "CSS Autonomous Trading")
    proposed = next(d for d in w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions if d.outcome == "PROPOSED")
    with pytest.raises(ProposalError, match="proposal_not_found"):
        w.router.decide_proposal("auto-1", w.sessions["auto-1"], proposed.proposal_id, approve=True, now=NOW)


# ------------------------------------------------------------------ manual orders
def _order(**kw):
    return {"symbol": "EUR/USD", "asset_class": "FX", "side": "BUY", "notional": 400.0, "stop_distance_pct": 2.5,
            "client_order_id": "c1", **kw}


def test_manual_order_without_css_assessment_rejected(tmp_path):
    w = World(tmp_path)
    w.user("assist-1", "CSS-Assisted Trading")
    d = w.router.submit_manual_order("assist-1", w.sessions["assist-1"], _order(), now=NOW)
    assert (d.outcome, d.stage, d.reason) == ("REJECTED", "routing", "manual_order_requires_css_market_assessment")


def test_manual_order_in_assisted_mode_requires_confirmation(tmp_path):
    w = World(tmp_path)
    w.assessment = ASSESSMENT
    w.user("assist-1", "CSS-Assisted Trading")
    d = w.router.submit_manual_order("assist-1", w.sessions["assist-1"], _order(), now=NOW)
    assert d.outcome == "PROPOSED" and w.book.positions() == []
    confirmed = w.router.decide_proposal("assist-1", w.sessions["assist-1"], d.proposal_id, approve=True, now=NOW)
    assert confirmed.outcome == "COPIED"


@pytest.mark.parametrize("mode,reason", [
    ("CSS Autonomous Trading", "autonomous_mode_accepts_css_engine_signals_only"),
])
def test_manual_orders_not_accepted_in_delegated_modes(tmp_path, mode, reason):
    w = World(tmp_path)
    w.assessment = ASSESSMENT
    w.user("auto-1", mode)
    d = w.router.submit_manual_order("auto-1", w.sessions["auto-1"], _order(), now=NOW)
    assert (d.stage, d.reason) == ("authority", reason)


def test_manual_order_without_acceptance_rejected(tmp_path):
    w = World(tmp_path)
    w.assessment = ASSESSMENT
    d = w.router.submit_manual_order("assist-1", w.sessions["assist-1"], _order(), now=NOW)
    assert (d.stage, d.reason) == ("consent", "consent_missing")


# ------------------------------------------------------------------ fail-closed context
def test_no_current_sign_on_session_rejected(tmp_path):
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading")
    del w.sessions["auto-1"]
    (d,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
    assert (d.stage, d.reason) == ("routing", "no_current_sign_on_session")


def test_stale_sign_on_session_rejected_by_r7(tmp_path):
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading")
    w.sessions["auto-1"] = (SESSION, time.time() - 7200)
    (d,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
    assert (d.stage, d.reason) == ("css_unified_trade_gate", "rejected: session expired")  # canonical R7 check


def test_unknown_role_rejected(tmp_path):
    w = World(tmp_path)
    ROLES_BACKUP = dict(ROLES)
    try:
        w.user("auto-1", "CSS Autonomous Trading")
        ROLES.pop("auto-1")
        (d,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
        assert (d.stage, d.reason) == ("routing", "role_unknown")
    finally:
        ROLES.clear()
        ROLES.update(ROLES_BACKUP)


def test_safety_flag_provider_failure_fails_closed(tmp_path):
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading")
    w.system = RuntimeError("launcher unavailable")
    (d,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
    assert (d.stage, d.reason) == ("routing", "safety_flags_unavailable")


def test_unsafe_flags_block_all_routes(tmp_path):
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading")
    w.system = system(safety_flags={**SAFE_FLAGS, "execution_allowed": True})
    (d,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
    assert (d.stage, d.reason) == ("safety", "safety_flags_not_safe")


def test_pilot_scope_book_is_bounded_by_envelope_and_antibleed(tmp_path):
    w = World(tmp_path, pilot=True)
    w.user("auto-1", "CSS Autonomous Trading")
    (d,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
    assert d.notional == 19.99 and d.reason == "anti_bleed_guard:trade_size_too_small" and w.book.positions() == []


def test_capital_governor_gate_rejection_is_enforced(tmp_path, monkeypatch):
    from backend.app.risk import unified_risk_execution_gate as urg
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading")
    real = urg.UnifiedRiskExecutionGate.evaluate

    def deny(self, **kw):
        return real(self, **{**kw, "available_capital": 0.0})  # governor sees no capital
    monkeypatch.setattr(urg.UnifiedRiskExecutionGate, "evaluate", deny)
    (d,) = w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions
    assert (d.outcome, d.stage) == ("REJECTED", "capital_governor") and "NO_AVAILABLE_CAPITAL" in d.reason


# ------------------------------------------------------------------ exits
def test_exit_cycle_closes_positions_even_after_consent_lost(tmp_path):
    w = World(tmp_path)
    w.copy_user("copy-1")
    w.router.on_trader_signal(_envelope(), now=NOW)
    (pos,) = w.book.positions("copy-1")
    w.engine.preferences.pause("copy-1")
    w.engine.mandates.revoke(pos.mandate_id, follower_user_id="copy-1", reason="user", now=NOW)
    assert w.router.run_exit_cycle({"EUR/USD": pos.entry_price}, now=NOW + timedelta(minutes=1)) == []  # holds
    closed = w.router.run_exit_cycle({"EUR/USD": pos.entry_price * 0.9}, now=NOW + timedelta(minutes=2))
    assert [(c["user_id"], c["reason"]) for c in closed] == [("copy-1", "STOP_LOSS")] and closed[0]["pnl"] < 0
    acct = w.book.account("copy-1", NOW)
    assert acct["realized_pnl"] == closed[0]["pnl"] and w.book.positions() == []
    assert reconcile(w.engine.ledger.records())["counts"]["exits"] == 1


def test_exit_cycle_without_mark_holds(tmp_path):
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading")
    w.router.on_css_engine_signal(_engine_signal(), now=NOW)
    assert w.router.run_exit_cycle({}, now=NOW) == [] and len(w.book.positions()) == 1


def test_open_positions_count_toward_next_decision(tmp_path):
    w = World(tmp_path)
    w.user("auto-1", "CSS Autonomous Trading", "Safe")  # Safe: 2 open positions max, FX only
    decisions = [w.router.on_css_engine_signal(_engine_signal(signal_id=f"s{i}", symbol=f"EUR/US{i}",
                                                              probability=0.8, strategy_score=0.95,
                                                              replay_confidence=0.95, risk_reward=3.0), now=NOW).decisions[0]
                 for i in range(3)]
    assert [d.outcome for d in decisions] == ["COPIED", "COPIED", "REJECTED"]
    assert (decisions[2].stage, decisions[2].reason) == ("exposure", "personality_open_position_limit")
    assert len(w.book.positions("auto-1")) == 2


# ------------------------------------------------------------------ HTTP endpoints
def _client(w):
    def resolver(request):
        uid = request.headers.get("x-test-user")
        return {"user_id": uid, "session_id": SESSION, "session_created": time.time(), "role": ROLES.get(uid)} if uid else None

    app = FastAPI()
    app.include_router(create_trading_profiles_router(
        user_resolver=resolver, service_factory=lambda: TradingProfileService(w.root, key_provider=lambda: KEY),
        router_factory=lambda: w.router))
    return TestClient(app)


def test_http_assisted_flow_and_paper_book(tmp_path):
    w = World(tmp_path)
    w.user("assist-1", "CSS-Assisted Trading")
    w.router.on_css_engine_signal(_engine_signal(), now=NOW)
    c = _client(w)
    h = {"x-test-user": "assist-1"}
    (proposal,) = c.get(PREFIX + "/proposals", headers=h).json()["proposals"] or [None]
    assert proposal is not None
    assert c.post(f"{PREFIX}/proposals/{proposal['proposal_id']}/decision", headers=h, json={"approve": "yes"}).status_code == 400
    r = c.post(f"{PREFIX}/proposals/{proposal['proposal_id']}/decision", headers=h, json={"approve": True}).json()
    assert r["decision"]["outcome"] == "COPIED"
    book = c.get(PREFIX + "/paper/book", headers=h).json()
    assert len(book["positions"]) == 1 and book["live_trading"] is False


def test_http_proposals_isolated_per_user(tmp_path):
    w = World(tmp_path)
    w.user("assist-1", "CSS-Assisted Trading")
    w.router.on_css_engine_signal(_engine_signal(), now=NOW)
    c = _client(w)
    assert c.get(PREFIX + "/proposals", headers={"x-test-user": "auto-1"}).json()["proposals"] == []
    assert c.get(PREFIX + "/proposals").status_code == 401


def test_http_trader_registry_requires_super_user_and_dual_control(tmp_path):
    w = World(tmp_path)
    c = _client(w)
    body = {"trader_id": "trader-gamma", "display_name": "Synthetic gamma", "public_key_b64": public_key_b64("trader-gamma"),
            "asset_classes": ["FX"]}
    assert c.post(PREFIX + "/admin/traders", headers={"x-test-user": "copy-1"}, json=body).status_code == 403
    assert c.post(PREFIX + "/admin/traders", headers={"x-test-user": "admin-a"}, json=body).json()["trader"]["status"] == "PENDING"
    r = c.post(PREFIX + "/admin/traders/trader-gamma/approve", headers={"x-test-user": "admin-a"}, json={})
    assert r.status_code == 400 and r.json()["reason"] == "dual_control_requires_different_approver"
    r = c.post(PREFIX + "/admin/traders/trader-gamma/approve", headers={"x-test-user": "admin-b"}, json={})
    assert r.json()["trader"]["status"] == "ACTIVE"
    assert c.post(PREFIX + "/admin/traders/trader-gamma/delete", headers={"x-test-user": "admin-b"}, json={}).status_code == 404
    listed = c.get(PREFIX + "/admin/traders", headers={"x-test-user": "admin-b"}).json()["traders"]
    assert [t["trader_id"] for t in listed] == ["trader-gamma"] and "public_key_b64" not in listed[0]


def test_http_feed_requires_valid_signature(tmp_path):
    w = World(tmp_path)
    w.copy_user("copy-1")
    c = _client(w)
    bad = _envelope(signal_id="sig-http")
    bad["signature_b64"] = sign_signal(trader_key("someone-else"), bad["payload"])["signature_b64"]
    assert c.post(PREFIX + "/feed/signals", json=bad).status_code == 403
    # A freshly issued signal (the HTTP route uses the real clock for freshness).
    from datetime import datetime, timezone
    good = _envelope(signal_id="sig-http-2", issued_at_utc=datetime.now(timezone.utc).isoformat())
    r = c.post(PREFIX + "/feed/signals", json=good).json()
    assert r["ok"] and r["followers_evaluated"] == 1


def test_routes_never_produce_live_or_broker_status(tmp_path):
    w = World(tmp_path)
    w.copy_user("copy-1")
    w.user("auto-1", "CSS Autonomous Trading")
    decisions = list(w.router.on_trader_signal(_envelope(), now=NOW).decisions)
    decisions += list(w.router.on_css_engine_signal(_engine_signal(), now=NOW).decisions)
    assert decisions and all(d.pipeline_status in {None, "validated_not_executed", "simulated_not_routed", "blocked"}
                             for d in decisions)
    assert all(replace(d).fill is None or d.fill["source"] == "SIMULATED_PAPER_FILL" for d in decisions)
