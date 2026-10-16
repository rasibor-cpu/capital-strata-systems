"""Operational readiness: preflight gating, R7 re-attestation, CLI refusals. No network."""
from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_css_rc1_signals import ADMIN_A, ADMIN_B, H, _artifact, _now_for, synthetic
from backend.signals.candles import CandleError
from backend.signals.producer import CalibrationApprovals
from backend.simulation import cad146
from backend.simulation.preflight import run_preflight

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("css_sim_cad146_tool", REPO / "tools" / "css_sim_cad146.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

SAFE_ENV = {"CSS_LIVE_ORDER_KILL_SWITCH": "1"}


def _live():
    return replace(synthetic(), classification="LIVE")


def _quote(now):
    return lambda inst: SimpleNamespace(spread_bps=0.5, exchange_ts=now)


def _pf(tmp_path, *, env=SAFE_ENV, fetch=None, artifacts=None, capital=14_600.0, approve=False, root=None,
        modules=("backend.simulation.cad146", "backend.oms.paper_oms")):
    s = _live()
    now = _now_for(s)
    arts = [_artifact()] if artifacts is None else artifacts
    if approve:
        appr = CalibrationApprovals(tmp_path / "ops")
        for a in arts:
            appr.approve(a, actor_ctx=ADMIN_A)
            appr.approve(a, actor_ctx=ADMIN_B)
    return run_preflight(root=root or tmp_path / "run", artifacts=arts, approvals_root=tmp_path / "ops",
                         fetch=fetch or (lambda i, g: s), quote=_quote(now), server_time=lambda: now,
                         capital_cad=capital, env=env, now=now, local_clock=lambda: now,
                         loaded_modules=modules)


def _status(result):
    return {c["name"]: c["status"] for c in result["checks"]}


def test_preflight_passes_only_with_every_required_condition(tmp_path):
    ok = _pf(tmp_path)
    st = _status(ok)
    assert ok["verdict"] == "PASS" and st["track_a_routable_artifacts"] == "WARN"  # unapproved: reported, not blocking
    assert ok["observations"][0]["data_sha256"] and ok["real_orders"] == 0
    assert _status(_pf(tmp_path, approve=True))["track_a_routable_artifacts"] == "PASS"


@pytest.mark.parametrize("case,check", [
    ("live_switch_off", "live_kill_switch_engaged"),
    ("sim_halted", "sim_entries_enabled"),
    ("live_armed", "no_live_arming"),
    ("global_stop", "global_emergency_stop_clear"),
    ("no_artifacts", "calibration_artifacts_present"),
    ("wrong_capital", "engineering_capital"),
    ("data_down", "market_data:BTC-USD:3600"),
    ("stale", "market_data:BTC-USD:3600"),
    ("synthetic", "market_data:BTC-USD:3600"),
    ("operational_root", "ledger_isolation"),
    ("broker_loaded", "broker_isolation"),
])
def test_preflight_fails_closed(tmp_path, case, check):
    kw = {}
    s = _live()
    if case == "live_switch_off":
        kw["env"] = {}
    elif case == "sim_halted":
        kw["env"] = {**SAFE_ENV, "CSS_SIM_ENTRY_HALT": "1"}
    elif case == "live_armed":
        kw["env"] = {**SAFE_ENV, "REA_LIVE_ARM": "true"}
    elif case == "global_stop":
        kw["env"] = {**SAFE_ENV, "REA_KILL_SWITCH": "1"}
    elif case == "no_artifacts":
        kw["artifacts"] = []
    elif case == "wrong_capital":
        kw["capital"] = 100_000.0
    elif case == "data_down":
        kw["fetch"] = lambda i, g: (_ for _ in ()).throw(CandleError("fetch_failed_after_retries:ProxyError"))
    elif case == "stale":
        kw["fetch"] = lambda i, g: replace(s, candles=s.candles[:-5])
    elif case == "synthetic":
        kw["fetch"] = lambda i, g: replace(s, classification="SYNTHETIC")
    elif case == "broker_loaded":
        kw["modules"] = ("backend.app.brokers.oanda_adapter",)
    elif case == "operational_root":
        kw["root"] = cad146._REPO_ROOT / "artifacts" / "trading_profiles" / "sim"
    result = _pf(tmp_path, **kw)
    assert result["verdict"] == "FAIL" and _status(result)[check] == "FAIL", result["checks"]


def _args(tmp_path, **kw):
    base = dict(root=str(tmp_path / "run"), artifacts=str(tmp_path / "arts"), approvals_root=str(tmp_path / "ops"),
                operator="robert", capital_profile="engineering", custom_capital_cad=None, source="coinbase",
                hours=0.0, poll_seconds=0.0, out=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_run_never_starts_the_clock_when_preflight_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_preflight", lambda args, now=None: {"verdict": "FAIL", "checks": []})
    with pytest.raises(SystemExit):
        tool.cmd_run(_args(tmp_path), presenter=lambda p: True)
    assert not (tmp_path / "run" / "run.json").exists()


def test_run_starts_only_after_preflight_pass_and_records_it(tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "_preflight", lambda args, now=None: {"verdict": "PASS", "checks": [], "x": 1})
    monkeypatch.setattr(tool, "CoinbaseQuotes", lambda http: None)
    assert tool.cmd_run(_args(tmp_path), presenter=lambda p: True) == 0
    meta = json.loads((tmp_path / "run" / "run.json").read_text())
    assert meta["starting_equity_cad"] == 14_600.0
    assert json.loads((tmp_path / "run" / "preflight.json").read_text())["verdict"] == "PASS"


def test_reattestation_requires_present_operator_and_existing_run(tmp_path, monkeypatch):
    args = _args(tmp_path)
    with pytest.raises(SystemExit, match="no simulation initialised"):
        tool.cmd_attest(args, confirm=lambda: "robert")
    monkeypatch.setattr(tool, "_preflight", lambda a, now=None: {"verdict": "PASS", "checks": []})
    monkeypatch.setattr(tool, "CoinbaseQuotes", lambda http: None)
    tool.cmd_run(args, presenter=lambda p: True)
    session = tmp_path / "run" / "operator_session.json"
    before = json.loads(session.read_text())["created"]
    with pytest.raises(SystemExit, match="not confirmed"):
        tool.cmd_attest(args, confirm=lambda: "someone-else")
    assert json.loads(session.read_text())["created"] == before
    assert tool.cmd_attest(args, confirm=lambda: "robert") == 0
    assert json.loads(session.read_text())["created"] >= before


def test_report_flags_cycles_where_r7_sign_on_had_expired(tmp_path):
    from backend.signals.research import DEFAULT_COSTS

    s = _live()
    appr = CalibrationApprovals(tmp_path / "ops")
    art = _artifact()
    appr.approve(art, actor_ctx=ADMIN_A)
    appr.approve(art, actor_ctx=ADMIN_B)
    sim = cad146.Cad146Simulation(tmp_path / "sim", artifacts=[art], costs=DEFAULT_COSTS,
                                  operational_approvals_root=tmp_path / "ops", operator="robert",
                                  starting_equity=14_600.0, presenter=lambda p: True)
    sim.attest_operator("robert", now=_now_for(s) - timedelta(hours=2))
    sim.cycle(lambda i, g: s, [("BTC-USD", H)], now=_now_for(s))
    rep = sim.report()
    assert rep["cycles_with_expired_sign_on"] == 1 and rep["tracks"]["A_STRICT_GOVERNED"]["fills"] == 0
