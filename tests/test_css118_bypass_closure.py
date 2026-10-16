"""Closeout C4: legacy bypasses of the governed router are closed (paper only, fail closed).

- Mobile /trade: every ticket is a governed manual paper order via TradingRouter; broker
  (live or practice) tickets are refused; the legacy executor is unreachable from routes.
- Legacy dashboard loop: its automatic broker branch is closed in code.
- Standalone direct-broker scripts refuse to run before reading config or touching the network.
"""
from __future__ import annotations

import ast
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from css118_support import KEY, activate, signal
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from backend.trading_profiles.router import PaperBook, TradingRouter
from backend.trading_profiles.service import TradingProfileService
from css118_support import system as css_system
from dashboard.mobile import mobile_app

REPO = Path(__file__).resolve().parents[1]
PASSWORD = "synthetic-password"


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    root = tmp_path / "tp"
    service = TradingProfileService(root, key_provider=lambda: KEY)
    engine = CopyTradeEngine(root, key_provider=lambda: KEY)
    router = TradingRouter(engine, book=PaperBook(root), role_resolver=lambda u: "TRADER",
                           session_resolver=lambda u: None, system_provider=lambda: css_system())
    monkeypatch.setattr(mobile_app, "_trading_profiles_service", lambda: TradingProfileService(root, key_provider=lambda: KEY))
    monkeypatch.setattr(mobile_app, "_trading_router", lambda: router)
    monkeypatch.setattr(mobile_app, "_SESSIONS", {})
    monkeypatch.setattr(mobile_app, "_SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "load_users", lambda: {})
    monkeypatch.setattr(mobile_app, "save_users", lambda users: None)
    monkeypatch.setattr(mobile_app, "authenticate_credentials",
                        lambda users, uid, pw: {"user_id": uid, "role": "SUPER_USER", "display_name": uid})

    def forbidden(*a, **k):
        raise AssertionError("legacy mobile ticket executor must not be reachable")
    monkeypatch.setattr(mobile_app, "execute_mobile_trade_ticket", forbidden)
    controls = tmp_path / "controls.json"
    return {"client": TestClient(mobile_app.app, follow_redirects=False), "service": service, "router": router,
            "controls": controls, "events": tmp_path / "events.jsonl"}


def _login(env, user, mode="MOBILE_PAPER_TRADING", personality=("Simulated Trading", None)):
    env["controls"].write_text(json.dumps({"mobile_trading_mode": mode, "engine_mode": "BALANCED"}))
    activate(env["service"].consent, user, *personality)
    env["client"].post("/login", data={"user_id": user, "password": PASSWORD})


def _ticket(**kw):
    return {"symbol": "EUR/USD", "asset_class": "FX", "side": "BUY", "amount": "300", "stop_distance_pct": "1.5",
            "broker": "CSS_PAPER", **kw}


def test_paper_ticket_is_a_governed_manual_order(app_env):
    from datetime import datetime, timezone
    # CSS assessment at the real clock: the HTTP route evaluates freshness against real time.
    app_env["router"].on_css_engine_signal(signal(trader_id=AUTONOMOUS_SOURCE_ID), now=datetime.now(timezone.utc))
    _login(app_env, "u1")
    r = app_env["client"].post("/trade", data=_ticket())
    assert r.status_code == 200 and "CSS_GOVERNED_" in r.text
    events = [json.loads(line) for line in app_env["events"].read_text().splitlines()]
    governed = [e for e in events if e["event_type"] == "mobile_governed_ticket"]
    assert governed and governed[-1]["live_order_sent"] is False
    assert (governed[-1]["status"], governed[-1]["decision"]["reason"]) == ("CSS_GOVERNED_SIMULATED", "all_gates_passed")
    assert governed[-1]["decision"]["notional"] == 300.0  # the user's size
    (position,) = app_env["router"].book.positions("u1")
    assert position.symbol == "EUR/USD" and position.notional == 300.0


def test_paper_ticket_without_css_assessment_is_rejected_not_filled(app_env):
    _login(app_env, "u1")
    r = app_env["client"].post("/trade", data=_ticket())
    assert "CSS_GOVERNED_REJECTED" in r.text and "manual_order_requires_css_market_assessment" in r.text
    assert app_env["router"].book.positions() == []


@pytest.mark.parametrize("mode,broker", [("MOBILE_LIVE_TRADING_ARMED", "OANDA"), ("MOBILE_LIVE_TRADING_ARMED", "COINBASE"),
                                         ("MOBILE_PAPER_TRADING", "OANDA")])
def test_broker_tickets_are_refused(app_env, mode, broker):
    _login(app_env, "u1", mode=mode)
    r = app_env["client"].post("/trade", data=_ticket(broker=broker, confirm="MOBILE LIVE"))
    assert r.status_code == 403 and "LIVE_TICKET_DISABLED_CSS118" in r.text
    assert app_env["router"].book.positions() == []


def test_read_only_mode_refuses_tickets(app_env):
    _login(app_env, "u1", mode="MOBILE_READ_ONLY")
    r = app_env["client"].post("/trade", data=_ticket())
    assert r.status_code == 403 and "MOBILE_ORDERS_DISABLED" in r.text


def test_no_route_calls_the_legacy_executor():
    tree = ast.parse((REPO / "dashboard" / "mobile" / "mobile_app.py").read_text(encoding="utf-8"))
    callers = {fn.name for fn in ast.walk(tree) if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
               for node in ast.walk(fn) if isinstance(node, ast.Call)
               and getattr(node.func, "id", None) == "execute_mobile_trade_ticket"}
    assert callers == set()


def test_legacy_dashboard_loop_broker_branch_is_closed_in_code():
    source = (REPO / "scripts" / "css_live_dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    consts = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and isinstance(n.value, ast.Constant)}
    assert consts["LEGACY_LOOP_BROKER_EXECUTION_PERMITTED"] is False
    branch = source.index('if position.get("broker_tested"):')
    window = source[branch:branch + 1200]
    assert "if not LEGACY_LOOP_BROKER_EXECUTION_PERMITTED:" in window
    assert window.index("LEGACY_LOOP_BROKER_PATH_DISABLED_CSS118") < window.index("attempt_oanda_fx_execution")


def test_legacy_dashboard_random_candidate_opens_are_retired():
    """CSS-118 B5: random candidates must not open operator paper positions."""
    source = (REPO / "scripts" / "css_live_dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    consts = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and isinstance(n.value, ast.Constant)}
    assert consts["LEGACY_LOOP_RANDOM_CANDIDATE_OPENS_PERMITTED"] is False
    assert "elif not LEGACY_LOOP_RANDOM_CANDIDATE_OPENS_PERMITTED:" in source
    # Import-time constant gates select_cycle_candidates to [].
    import importlib
    import sys
    sys.modules.pop("scripts.css_live_dashboard", None)
    # The dashboard module is heavy; assert via AST that the empty-return guard exists.
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "select_cycle_candidates")
    src_fn = ast.get_source_segment(source, fn) or ""
    # Reconciled with RC1 R3 (stricter than the B5 flag): the generator is unconditionally
    # empty, so flipping the flag alone can never re-enable random opens.
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    assert len(returns) == 1 and isinstance(returns[0].value, ast.List) and returns[0].value.elts == []
    assert not [n for n in ast.walk(fn) if isinstance(n, ast.Call)]  # no random.choice/shuffle


def test_run_live_manual_remains_retired_at_import():
    import importlib
    import sys
    sys.modules.pop("run_live_manual", None)
    with pytest.raises(SystemExit, match="NON-CANONICAL RETIREMENT CANDIDATE"):
        importlib.import_module("run_live_manual")


@pytest.mark.parametrize("module_name", ["backend.app.oanda_trade_smoketest"])
def test_direct_broker_scripts_refuse_before_any_config_or_network(module_name, monkeypatch, capsys):
    import importlib

    import requests

    def no_network(*a, **k):
        raise AssertionError("network must not be touched")
    for verb in ("get", "post", "put", "request"):
        monkeypatch.setattr(requests, verb, no_network)
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no config read")))
    mod = importlib.import_module(module_name)
    assert mod.main() == 3
    assert "REFUSED" in capsys.readouterr().err


def test_direct_broker_guard_is_a_code_constant():
    from backend.runtime import direct_broker_script_guard as guard
    assert guard.DIRECT_BROKER_SCRIPTS_PERMITTED is False


def test_emergency_risk_reduction_still_works_without_acceptance(app_env, tmp_path):
    app_env["controls"].write_text(json.dumps({"mobile_trading_mode": "MOBILE_PAPER_TRADING", "engine_mode": "SAFE"}))
    app_env["client"].post("/login", data={"user_id": "never-accepted", "password": PASSWORD})
    r = app_env["client"].post("/controls", data={"mobile_trading_mode": "MOBILE_READ_ONLY", "engine_mode": "SAFE",
                                                  "live_order_kill_switch": "on"})
    assert r.status_code == 200
    saved = json.loads(app_env["controls"].read_text())
    assert saved["live_order_kill_switch"] is True and saved["mobile_trading_mode"] == "MOBILE_READ_ONLY"
    assert time.time() > 0
