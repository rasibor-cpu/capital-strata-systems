"""Validation of the two-track simulation with capital profiles (CAD 14,600 engineering trial).

Synthetic bars explicitly labelled LIVE exercise mechanics only; no market performance is implied.
"""
from __future__ import annotations

import importlib.util
import json
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_css_rc1_signals import ADMIN_A, ADMIN_B, H, _artifact, _now_for, synthetic
from css118_support import KEY, NOW, SESSION, activate, signal, system
from backend.signals.producer import CalibrationApprovals
from backend.signals.research import DEFAULT_COSTS
from backend.simulation import cad146
from backend.simulation.cad146 import TRACK_A, TRACK_B, Cad146Simulation, SIM_USER
from backend.simulation.capital_profiles import reference_comparison, starting_capital
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from backend.trading_profiles.router import DEFAULT_PAPER_EQUITY_CAD, PaperBook, PaperBookError, TradingRouter

REPO = Path(__file__).resolve().parents[1]
ENGINEERING = starting_capital(profile="engineering")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH", *cad146.LIVE_ARM_ENVS):
        monkeypatch.delenv(name, raising=False)


def make(tmp_path, *, approved, art=None, equity=ENGINEERING, name="sim"):
    art = art or _artifact()
    ops = tmp_path / f"ops-{name}"
    if approved:
        appr = CalibrationApprovals(ops)
        appr.approve(art, actor_ctx=ADMIN_A)
        appr.approve(art, actor_ctx=ADMIN_B)
    sim = Cad146Simulation(tmp_path / name, artifacts=[art], costs=DEFAULT_COSTS, operational_approvals_root=ops,
                           operator="operator-1", starting_equity=equity, presenter=lambda page: True)
    return sim, art


def live():
    return replace(synthetic(), classification="LIVE")


# ------------------------------------------------------------------ capital configuration
def test_customer_default_is_100k_and_engineering_trial_is_14600(tmp_path):
    assert DEFAULT_PAPER_EQUITY_CAD == 100_000.0
    assert PaperBook(tmp_path / "cust").account("u", NOW)["equity"] == 100_000.0
    assert ENGINEERING == 14_600.0
    sim, _ = make(tmp_path, approved=False)
    for track in (sim.track_a, sim.track_b):
        assert track.router.book.account(SIM_USER, NOW)["equity"] == 14_600.0  # not the customer default
    assert json.loads(sim.meta_path.read_text())["starting_equity_cad"] == 14_600.0


def test_canonical_customer_router_uses_the_100k_default():
    import dashboard.mobile.mobile_app as m
    assert m._trading_router().book.starting_equity == 100_000.0


# ------------------------------------------------------------------ two tracks at CAD 14,600
def test_engineering_capital_clears_antibleed_and_track_a_trades_only_when_approved(tmp_path):
    s = live()
    gov, _ = make(tmp_path, approved=True, name="approved")
    gov.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep = gov.report()
    a, b = rep["tracks"][TRACK_A], rep["tracks"][TRACK_B]
    assert a["fills"] == 1 and b["fills"] == 1
    (pos,) = a["open_positions"]
    assert 50 <= pos["notional_cad"] <= 0.05 * ENGINEERING + 0.01  # above AntiBleed min, within governor

    unapproved, _ = make(tmp_path, approved=False, name="unapproved")
    unapproved.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep2 = unapproved.report()
    assert rep2["tracks"][TRACK_A]["fills"] == 0  # no unauthorized trades
    assert rep2["tracks"][TRACK_B]["fills"] == 1 and rep2["tracks"][TRACK_B]["label"] == "RESEARCH_COUNTERFACTUAL"


def test_no_cross_contamination_between_tracks(tmp_path):
    s = live()
    sim, _ = make(tmp_path, approved=False)
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    a_book, b_book = sim.track_a.router.book, sim.track_b.router.book
    assert a_book.path != b_book.path and a_book.positions() == [] and len(b_book.positions()) == 1
    assert a_book.account(SIM_USER, NOW)["equity"] == ENGINEERING
    assert b_book.account(SIM_USER, NOW)["equity"] < ENGINEERING  # B paid its own entry fee
    a_ledger = [r for r in sim.track_a.router.engine.ledger.records()]
    b_ids = {p.position_id for p in b_book.positions()}
    assert not any(str(r.get("position_id")) in b_ids for r in a_ledger)
    rep = sim.report()
    assert rep["tracks"][TRACK_A]["decisions"] == 0 and rep["tracks"][TRACK_B]["decisions"] == 1


def test_identical_observation_feeds_both_tracks(tmp_path):
    s = live()
    sim, _ = make(tmp_path, approved=False)
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rows = [json.loads(x) for x in sim.journal.read_text().splitlines()]
    (obs,) = [r for r in rows if r["type"] == "OBSERVATION"]
    assert obs["data_sha256"] == s.digest
    produced = [r for r in rows if r["type"] == "PRODUCED"]
    assert {r["track"] for r in produced} == {TRACK_A, TRACK_B}
    assert all(r["at_utc"] == obs["at_utc"] for r in produced)


# ------------------------------------------------------------------ performance + normalisation
def test_report_metrics_and_reference_normalisation(tmp_path):
    s = live()
    sim, _ = make(tmp_path, approved=True)
    now = _now_for(s)
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=now)
    entry = sim.track_a.router.book.positions(SIM_USER)[0].entry_price
    loss_bar = replace(s.candles[-1], ts=s.candles[-1].ts + H, open=entry, high=entry, low=entry * 0.8,
                       close=entry * 0.8)
    s2 = replace(s, candles=s.candles + (loss_bar,))
    sim.cycle(lambda i, g: s2, [("BTC-USD", H)], now=now + timedelta(hours=1))
    rep = sim.report()
    a = rep["tracks"][TRACK_A]
    assert a["closed_trades"] == 1 and a["win_rate"] == 0.0 and a["net_pnl_cad"] < 0
    assert a["max_drawdown_cad"] == pytest.approx(ENGINEERING - min(ENGINEERING, a["equity_cad"]), abs=0.01)
    assert a["fees_cad"] > 0 and a["by_instrument"]["BTC-USD"]["closed"] == 1
    cmp = reference_comparison(a["net_pnl_cad"], simulation_capital_cad=ENGINEERING)
    assert cmp["scale_ratio"] == 100 and cmp["executable_at_reference_capital"] is False
    assert cmp["illustrative_reference_pnl_cad"] == pytest.approx(round(a["net_pnl_cad"] / 100, 2), abs=0.01)


def test_cli_refuses_resume_with_different_capital(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("css_sim_cad146", REPO / "tools" / "css_sim_cad146.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    monkeypatch.setattr(tool, "_terminal_presenter", lambda page: True)
    monkeypatch.setattr(tool, "CoinbaseQuotes", lambda http: None)
    monkeypatch.setattr(tool, "_preflight", lambda args, now=None: {"verdict": "PASS", "checks": []})
    root = tmp_path / "run"
    base = ["run", "--root", str(root), "--artifacts", str(tmp_path / "none"), "--approvals-root",
            str(tmp_path / "ops"), "--operator", "op", "--hours", "0"]
    assert tool.main(base + ["--capital-profile", "engineering"]) == 0
    with pytest.raises(SystemExit, match="initialised with CAD 14600.00"):
        tool.main(base + ["--capital-profile", "standard"])


# ------------------------------------------------------------------ safety
def test_sim_entry_halt_stops_simulated_entries_and_live_switch_does_not(tmp_path, monkeypatch):
    s = live()
    halted, _ = make(tmp_path, approved=True, name="halted")
    monkeypatch.setenv("CSS_SIM_ENTRY_HALT", "1")
    halted.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep = halted.report()
    assert all(t["fills"] == 0 and t["decisions"] == 0 for t in rep["tracks"].values())
    assert rep["sim_entry_halted_cycles"] == 1
    # Lifting the halt while the bar is current: the bar is decided (it was not marked processed).
    monkeypatch.delenv("CSS_SIM_ENTRY_HALT")
    monkeypatch.setenv("CSS_LIVE_ORDER_KILL_SWITCH", "1")  # live brokerage stays killed
    halted.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep = halted.report()
    assert rep["tracks"][TRACK_A]["fills"] == 1 and rep["live_kill_switch_engaged_all_cycles"] is False
    assert [json.loads(x) for x in halted.journal.read_text().splitlines() if '"HEARTBEAT"' in x][-1][
        "live_kill_switch_engaged"] is True


def test_global_emergency_stop_still_halts_simulation(tmp_path, monkeypatch):
    s = live()
    sim, _ = make(tmp_path, approved=True)
    monkeypatch.setenv("REA_KILL_SWITCH", "1")
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    for t in sim.report()["tracks"].values():
        assert t["fills"] == 0 and any("kill_switch" in k for k in t["reasons"]), t["reasons"]


def test_live_kill_switch_still_blocks_the_canonical_router(tmp_path, monkeypatch):
    """Separation is local to the simulation harness: the operational router is unchanged."""
    monkeypatch.setenv("CSS_LIVE_ORDER_KILL_SWITCH", "1")
    root = tmp_path / "tp"
    engine = CopyTradeEngine(root, key_provider=lambda: KEY)
    router = TradingRouter(engine, book=PaperBook(root), role_resolver=lambda u: "TRADER",
                           session_resolver=lambda u: (SESSION, time.time()), system_provider=lambda: system())
    activate(engine.consent, "auto-1", "CSS Autonomous Trading", "Balanced")
    (d,) = router.on_css_engine_signal(signal(trader_id=AUTONOMOUS_SOURCE_ID), now=NOW).decisions
    assert d.outcome == "REJECTED" and "kill_switch" in d.reason


def test_r14f_low_quality_signal_is_rejected_in_both_tracks(tmp_path):
    art = _artifact()
    body = {k: v for k, v in art.items() if k != "artifact_sha256"}
    body["quality_inputs"] = {"strategy_score": 0.0, "replay_confidence": 0.0}
    body["score_map"] = {"intercept": 0.0, "per_bps": 0.0}  # R14F signal score 0
    from backend.signals.calibration import artifact_digest
    weak = {**body, "artifact_sha256": artifact_digest(body)}
    s = live()
    sim, _ = make(tmp_path, approved=True, art=weak)
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    for t in sim.report()["tracks"].values():
        assert t["fills"] == 0 and t["rejected"] == 1, t["reasons"]


# ------------------------------------------------------------------ audited capital reset
def test_capital_reset_is_authorised_audited_and_tamper_evident(tmp_path):
    book = PaperBook(tmp_path / "b")
    book.account("u1", NOW)
    with pytest.raises(PaperBookError, match="reset_not_authorized"):
        book.reset_account("u1", capital_cad=25_000, actor_ctx={"user_id": "u2", "role": "TRADER"},
                           reason="x", now=NOW)
    with pytest.raises(PaperBookError, match="simulated_capital_out_of_range"):
        book.reset_account("u1", capital_cad=146, actor_ctx={"user_id": "u1", "role": "TRADER"}, reason="x", now=NOW)
    with pytest.raises(PaperBookError, match="reset_reason_required"):
        book.reset_account("u1", capital_cad=25_000, actor_ctx={"user_id": "u1", "role": "TRADER"}, reason=" ",
                           now=NOW)
    out = book.reset_account("u1", capital_cad=25_000, actor_ctx={"user_id": "u1", "role": "TRADER"},
                             reason="switch to intermediate", now=NOW)
    assert out["account"]["equity"] == 25_000 and out["account"]["resets"] == 1
    (ev,) = book.reset_history("u1")
    assert ev["prior_account"]["equity"] == 100_000.0 and ev["money_moved"] is False
    lines = (tmp_path / "b" / "paper_capital_resets.jsonl").read_text().splitlines()
    doc = json.loads(lines[0])
    doc["new_capital_cad"] = 1_000_000
    (tmp_path / "b" / "paper_capital_resets.jsonl").write_text(json.dumps(doc) + "\n")
    with pytest.raises(PaperBookError, match="chain_broken"):
        book.reset_history()


def test_capital_reset_refused_with_open_positions_or_pilot_envelope(tmp_path):
    root = tmp_path / "tp"
    engine = CopyTradeEngine(root, key_provider=lambda: KEY)
    router = TradingRouter(engine, book=PaperBook(root), role_resolver=lambda u: "TRADER",
                           session_resolver=lambda u: (SESSION, time.time()), system_provider=lambda: system())
    activate(engine.consent, "auto-1", "CSS Autonomous Trading", "Balanced")
    router.on_css_engine_signal(signal(trader_id=AUTONOMOUS_SOURCE_ID), now=NOW)
    assert router.book.positions("auto-1")
    with pytest.raises(PaperBookError, match="no_open_positions"):
        router.book.reset_account("auto-1", capital_cad=10_000, actor_ctx={"user_id": "auto-1", "role": "TRADER"},
                                  reason="r", now=NOW)
    pilot = PaperBook(tmp_path / "pilot", pilot_envelope=True)
    pilot.account("p", NOW)
    with pytest.raises(PaperBookError, match="pilot_envelope"):
        pilot.reset_account("p", capital_cad=10_000, actor_ctx={"user_id": "admin", "role": "SUPER_USER"},
                            reason="r", now=NOW)
