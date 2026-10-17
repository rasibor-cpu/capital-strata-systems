"""CAD 146 two-track simulation: isolation, governance, idempotency, restart, outage, R7 sign-on.

Bars are synthetic and explicitly labelled LIVE to exercise the mechanics; the real run uses
real providers (tools/css_sim_cad146.py). No broker is reachable from this code path.
"""
from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from agreement_support import accept_agreement

from test_css_rc1_signals import ADMIN_A, ADMIN_B, H, _artifact, _now_for, synthetic
from backend.signals.candles import CandleError
from backend.signals.producer import CalibrationApprovals
from backend.signals.research import DEFAULT_COSTS
from backend.simulation import cad146
from backend.simulation.cad146 import TRACK_A, TRACK_B, Cad146Simulation, SimulationError


@pytest.fixture(autouse=True)
def _no_ambient_switches(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH", *cad146.LIVE_ARM_ENVS):
        monkeypatch.delenv(name, raising=False)


def live(series):
    return replace(series, classification="LIVE")


def make(tmp_path, *, approved=False, equity=146.0, art=None):
    art = art or _artifact()
    ops = tmp_path / "ops_approvals"
    if approved:
        appr = CalibrationApprovals(ops)
        appr.approve(art, actor_ctx=ADMIN_A)
        appr.approve(art, actor_ctx=ADMIN_B)
    sim = Cad146Simulation(tmp_path / "sim", artifacts=[art], costs=DEFAULT_COSTS, operational_approvals_root=ops,
                           operator="operator-1", starting_equity=equity, presenter=accept_agreement)
    return sim, art


def events(sim, kind=None):
    rows = [json.loads(x) for x in sim.journal.read_text().splitlines()]
    return [r for r in rows if kind is None or r["type"] == kind]


def test_cad146_governed_sizing_is_below_antibleed_minimum_so_no_trade_occurs(tmp_path):
    sim, _ = make(tmp_path, approved=True)
    s = live(synthetic())
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep = sim.report()
    for name in (TRACK_A, TRACK_B):
        t = rep["tracks"][name]
        assert t["proposed_signals"] == 1 and t["fills"] == 0 and t["rejected"] == 1
        (reason,) = [k for k in t["reasons"] if "anti_bleed" in k]
        assert reason == "execution_gate:anti_bleed_guard:trade_size_too_small"
        assert t["equity_cad"] == 146.0 and t["net_pnl_cad"] == 0.0 and t["open_positions"] == []
    decision = [d for e in events(sim, "PRODUCED") if e["track"] == TRACK_A for d in e["decisions"]][0]
    assert decision["notional_cad"] < 50  # Balanced sizing on CAD 146 equity; AntiBleed minimum is CAD 50
    assert rep["run"]["risk_personality"] == "Balanced" and rep["run"]["operating_mode"] == "Simulated Trading"
    assert rep["run"]["real_orders"] == 0 and rep["run"]["safety_flags"]["execution_allowed"] is False


def test_track_a_requires_dual_approval_track_b_is_labelled_counterfactual_and_isolated(tmp_path):
    sim, _ = make(tmp_path, approved=False, equity=10_000.0)  # larger equity so sizing clears AntiBleed
    s = live(synthetic())
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep = sim.report()
    a, b = rep["tracks"][TRACK_A], rep["tracks"][TRACK_B]
    assert a["fills"] == 0 and a["reasons"] == {"calibration_not_routable:approvals_insufficient:0": 1}
    assert b["label"] == "RESEARCH_COUNTERFACTUAL" and b["fills"] == 1 and len(b["open_positions"]) == 1
    assert sim.track_a.router.book.positions() == []  # B's fill never appears in A
    assert sim.track_a.root != sim.track_b.root
    produced_b = [e for e in events(sim, "PRODUCED") if e["track"] == TRACK_B]
    assert produced_b and all(e["label"] == "RESEARCH_COUNTERFACTUAL" for e in produced_b)


def test_failed_gates_without_positive_expectancy_trade_in_neither_track(tmp_path):
    sim, _ = make(tmp_path, art=_artifact(positive=False), equity=10_000.0)
    s = live(synthetic())
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep = sim.report()
    assert rep["tracks"][TRACK_A]["fills"] == rep["tracks"][TRACK_B]["fills"] == 0


def test_replayed_bar_and_restart_never_duplicate_decisions_or_fills(tmp_path):
    sim, art = make(tmp_path, equity=10_000.0)
    s = live(synthetic())
    now = _now_for(s)
    first = sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=now)
    again = sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=now + timedelta(minutes=5))
    assert first["decisions"][TRACK_B] == 1 and again["decisions"] == {TRACK_A: 0, TRACK_B: 0}
    restarted = Cad146Simulation(tmp_path / "sim", artifacts=[art], costs=DEFAULT_COSTS,
                                 operational_approvals_root=tmp_path / "ops_approvals", operator="operator-1")
    assert restarted.cycle(lambda i, g: s, [("BTC-USD", H)], now=now + timedelta(minutes=10))["decisions"] == \
        {TRACK_A: 0, TRACK_B: 0}
    rep = restarted.report()
    assert rep["tracks"][TRACK_B]["fills"] == 1 and len(rep["tracks"][TRACK_B]["open_positions"]) == 1
    assert rep["run"]["starting_equity_cad"] == 10_000.0  # restart keeps the original run parameters


def test_data_outage_fails_safe(tmp_path):
    sim, _ = make(tmp_path, approved=True, equity=10_000.0)

    def down(_i, _g):
        raise CandleError("market_data_unavailable:proxy_403")
    summary = sim.cycle(down, [("BTC-USD", H), ("ETH-USD", H)], now=datetime.now(timezone.utc))
    assert summary["outages"] == 2 and summary["decisions"] == {TRACK_A: 0, TRACK_B: 0}
    rep = sim.report()
    assert rep["outage_count"] == 2 and all(t["decisions"] == 0 for t in rep["tracks"].values())


def test_r7_expired_operator_sign_on_blocks_entries(tmp_path):
    sim, _ = make(tmp_path, approved=True, equity=10_000.0)
    sim.attest_operator("operator-1", now=datetime.now(timezone.utc) - timedelta(hours=2))
    s = live(synthetic())
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep = sim.report()
    for t in rep["tracks"].values():
        assert t["fills"] == 0 and any("session" in k for k in t["reasons"]), t["reasons"]


def test_activation_requires_the_agreement_to_be_accepted(tmp_path):
    with pytest.raises(SimulationError, match="consent_activation_required"):
        Cad146Simulation(tmp_path / "s1", artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path,
                         operator="op")
    seen = []

    def quit_on_page_two(review):
        while True:
            seen.append(review.page()["page_id"])
            if len(seen) == 2:
                return  # walks away: no acceptance
            review.next()

    with pytest.raises(SimulationError, match="agreement_not_accepted:review_ended_without_acceptance"):
        Cad146Simulation(tmp_path / "s2", artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path,
                         operator="op", presenter=quit_on_page_two)
    assert len(seen) == 2 and not (tmp_path / "s2" / "run.json").exists()  # the 48-hour clock never started


def test_refuses_operational_book_and_live_arming(tmp_path, monkeypatch):
    with pytest.raises(SimulationError, match="operational_paper_book"):
        Cad146Simulation(cad146._REPO_ROOT / "artifacts" / "trading_profiles" / "sim", artifacts=[],
                         costs=DEFAULT_COSTS, operational_approvals_root=tmp_path, operator="op")
    monkeypatch.setenv("REA_LIVE_ARM", "true")
    with pytest.raises(SimulationError, match="live_arming_detected"):
        Cad146Simulation(tmp_path / "sim", artifacts=[], costs=DEFAULT_COSTS, operational_approvals_root=tmp_path,
                         operator="op")


def test_simulation_module_has_no_broker_path():
    import ast
    src = (cad146._REPO_ROOT / "backend" / "simulation" / "cad146.py").read_text(encoding="utf-8")
    imported = {n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m and ("broker" in m or "oms" in m or "execution_router" in m) for m in imported)
