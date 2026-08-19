import ast
import copy
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.runtime.capital_state import canonical_drawdown_display
from engine.performance.pnl_tracker import PnLTracker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"

FORBIDDEN_DISPLAY_CALLS = {
    "approve_trade_before_register",
    "r17_execute_exit",
    "book_position_exit",
    "place_paper_order",
    "place_broker_order",
    "submit_order",
    "submit_live_order",
    "coinbase_live_orders_enabled",
}

SAFETY_PATH_PREFIXES = (
    "engine/execution/",
    "engine/adapters/",
    "backend/app/risk/anti_bleed_guard.py",
    "backend/governance/css_unified_trade_gate.py",
    "backend/app/risk/capital_allocation_governor.py",
    "engine/risk/",
    "backend/brokers/",
    "engine/brokers/",
)


def _load_named_dashboard_functions(*names: str, extra_assigns: set[str] | None = None):
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = set(names)
    wanted_assigns = extra_assigns or set()
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            target_names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if target_names & wanted_assigns:
                nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            nodes.append(node)
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    return compile(module, str(DASHBOARD_PATH), "exec")


class _FakeMTM:
    def __init__(self, positions=None):
        self.positions = list(positions or [])

    def count_open_positions(self) -> int:
        return sum(1 for pos in self.positions if not pos.get("forced_exit"))

    def count_open_positions_by_asset(self) -> dict[str, int]:
        counts = {"CRYPTO": 0, "FX": 0, "FUTURES": 0, "OPTIONS": 0}
        for pos in self.positions:
            if pos.get("forced_exit"):
                continue
            asset = str(pos.get("asset_class", "UNKNOWN"))
            if asset in counts:
                counts[asset] += 1
        return counts

    def floating_by_asset(self, funded_only: bool = False) -> dict[str, float]:
        by_asset = {"CRYPTO": 0.0, "FX": 0.0, "FUTURES": 0.0, "OPTIONS": 0.0}
        for pos in self.positions:
            if pos.get("forced_exit"):
                continue
            if funded_only and not pos.get("broker_tested", False):
                continue
            asset = str(pos.get("asset_class", "UNKNOWN"))
            if asset in by_asset:
                by_asset[asset] += float(pos.get("floating", 0.0))
        return by_asset


def _authoritative_fixture():
    positions = [
        {"asset_class": "CRYPTO", "symbol": "BTC-USD", "floating": 0.0497, "forced_exit": False},
        {"asset_class": "FX", "symbol": "EUR_USD", "floating": 0.0500, "forced_exit": False},
    ]
    tracker = PnLTracker(starting_equity=200.0)
    tracker.current_equity = 201.1212
    tracker.peak_equity = 201.5609
    observer = SimpleNamespace(starting_balance=200.0, current_balance=201.1212)
    return {
        "positions": positions,
        "tracker": tracker,
        "observer": observer,
        "crypto_pnl": {"BTC-USD": 0.8000},
        "fx_pnl": {"EUR_USD": 0.2215},
        "futures_pnl": {},
        "options_pnl": {},
    }


def _load_command_dashboard_collect_namespace():
    fixture = _authoritative_fixture()
    compiled = _load_named_dashboard_functions(
        "collect_command_dashboard_snapshot",
        "command_dashboard_lines",
        "current_realized_pnl_maps_by_asset_category",
        "normalize_asset_category",
        "_safe_dashboard_float",
        "aggregate_pnl_by_asset_category",
    )
    namespace = {
        "Any": Any,
        "os": os,
        "time": time,
        "canonical_drawdown_display": canonical_drawdown_display,
        "mtm_engine": _FakeMTM(fixture["positions"]),
        "pnl_tracker": fixture["tracker"],
        "pnl_observer": fixture["observer"],
        "crypto_pnl": dict(fixture["crypto_pnl"]),
        "fx_pnl": dict(fixture["fx_pnl"]),
        "futures_pnl": dict(fixture["futures_pnl"]),
        "options_pnl": dict(fixture["options_pnl"]),
        "total_realized_pnl": lambda: round(1.0215, 4),
        "hard_position_limit": lambda: 10,
        "hard_asset_cap": lambda asset: {"CRYPTO": 3, "FX": 3, "FUTURES": 2, "OPTIONS": 2}[asset],
        "active_execution_scope_label": lambda: "PAPER ONLY",
        "broker_execution_status_label": lambda: "DISABLED",
        "pcnrass_read_mobile_controls": lambda: {"cycle_interval_seconds": 60},
        "is_session_locked": lambda: False,
        "SELECTED_BROKER_MODE": "paper",
        "ENGINE_MODE": "BALANCED",
        "SELECTED_BROKER": "NONE",
        "cycle": 3,
        "last_trade": "TAKE_PROFIT BTC-USD",
        "BROKER_EXECUTION_ARMED": False,
        "SESSION_USER_CTX": {
            "created": time.time() - 125,
            "role_profile": {
                "can_execute_paper_trading": True,
                "can_execute_live_trading": False,
            },
        },
        "capital_governor": SimpleNamespace(
            balance_snapshot={
                "capital_state": "SIMULATED_CAPITAL_READY",
                "drawdown_reason": "",
            }
        ),
        "_DIVERGENCE_STATE": {"pending_count": 0, "confirmed_count": 0},
    }
    exec(compiled, namespace)
    namespace["_fixture"] = fixture
    return namespace


def _load_render_helpers(tmp_path, positions=None):
    compiled = _load_named_dashboard_functions(
        "command_dashboard_lines",
        "current_realized_pnl_maps_by_asset_category",
        "normalize_asset_category",
        "_safe_dashboard_float",
        "aggregate_pnl_by_asset_category",
        "pnl_by_asset_category_dashboard_lines",
        "format_greeks_dashboard_value",
        "option_position_greeks_dashboard_lines",
        "portfolio_greeks_from_positions",
        "portfolio_greeks_dashboard_lines",
        "_format_margin_dashboard_value",
        "_margin_dashboard_mode_is_live",
        "_margin_dashboard_adapter_for_context",
        "margin_dashboard_lines",
        "render_trade_dashboard_summary",
        extra_assigns={
            "OPTION_GREEK_FIELDS",
            "VALID_GREEKS_SOURCES",
            "PORTFOLIO_GREEK_FIELDS",
        },
    )
    output = []
    namespace = {
        "Any": Any,
        "print": lambda *args, **_kwargs: output.append(" ".join(str(arg) for arg in args)),
        "canonical_drawdown_display": canonical_drawdown_display,
        "mtm_engine": SimpleNamespace(positions=positions or []),
        "crypto_pnl": {},
        "fx_pnl": {},
        "futures_pnl": {},
        "options_pnl": {},
        "MAX_PAPER_OPEN_POSITIONS": 10,
        "ENGINE_MODE": "BALANCED",
        "SELECTED_BROKER": "NONE",
        "SELECTED_BROKER_MODE": "paper",
        "cycle": 3,
        "last_trade": "NONE",
        "CLOSED_TRADE_LEDGER_PATH": tmp_path / "closed_trades.jsonl",
        "BROKER_EXECUTION_ARMED": False,
    }
    exec(compiled, namespace)
    namespace["_output"] = output
    return namespace


def _cow_snapshot() -> dict:
    return {
        "status": "RUNNING",
        "mode": "paper",
        "engine": "BALANCED",
        "cycle": 3,
        "broker": "NONE",
        "execution": "PAPER ONLY",
        "live_execute": "NO",
        "starting_balance": 200.0,
        "current_balance": 201.1212,
        "realized_pnl": 1.0215,
        "unrealized_pnl": 0.0997,
        "total_pnl": 1.1212,
        "tracker_equity": 201.1212,
        "peak_equity": 201.5609,
        "drawdown_display": "0.2200%",
        "positions_total": 10,
        "positions_limit": 10,
        "positions_by_asset": {"CRYPTO": 3, "FX": 3, "FUTURES": 2, "OPTIONS": 2},
        "caps_by_asset": {"CRYPTO": 3, "FX": 3, "FUTURES": 2, "OPTIONS": 2},
        "pnl_by_asset": {"CRYPTO": 0.8497, "FX": 0.2715, "FUTURES": 0.0, "OPTIONS": 0.0},
        "last_trade": "TAKE_PROFIT BTC-USD",
        "unified_trade_gate": "UNKNOWN",
        "margin_gate": "UNKNOWN",
        "margin_state": "UNKNOWN",
        "broker_execution": "DISABLED",
        "defensive_mode": "NO",
        "auto_flatten": "SIMULATION pending=0 confirmed=0",
        "kill_switch": "UNKNOWN",
        "cycle_interval": 60,
        "runtime_duration": "2m 05s",
        "health": "OK",
    }


def test_command_dashboard_uses_authoritative_realized_pnl():
    ns = _load_command_dashboard_collect_namespace()
    snapshot = ns["collect_command_dashboard_snapshot"]()
    lines = ns["command_dashboard_lines"](snapshot)
    rendered = "\n".join(lines)
    assert snapshot["realized_pnl"] == 1.0215
    assert "Realized P&L: +1.0215" in rendered


def test_command_dashboard_uses_authoritative_unrealized_pnl():
    ns = _load_command_dashboard_collect_namespace()
    snapshot = ns["collect_command_dashboard_snapshot"]()
    lines = ns["command_dashboard_lines"](snapshot)
    rendered = "\n".join(lines)
    assert snapshot["unrealized_pnl"] == 0.0997
    assert "Unrealized P&L: +0.0997" in rendered
    assert snapshot["total_pnl"] == 1.1212
    assert "Total P&L: +1.1212" in rendered


def test_tracker_equity_peak_drawdown_are_not_na_when_values_exist(tmp_path):
    ns = _load_render_helpers(tmp_path)
    ns["render_trade_dashboard_summary"](_cow_snapshot())
    rendered = "\n".join(ns["_output"])
    assert "Equity: +201.1212" in rendered
    assert "Peak Equity: +201.5609" in rendered
    assert "Drawdown: 0.2200%" in rendered
    assert "Tracker Equity: +201.1212" in rendered
    assert "Tracker Equity: N/A" not in rendered
    assert "Peak Equity: N/A" not in rendered
    assert "Drawdown: N/A" not in rendered


def test_collect_wires_tracker_from_pnl_tracker_not_missing_globals():
    ns = _load_command_dashboard_collect_namespace()
    assert "tracker_equity" not in ns
    snapshot = ns["collect_command_dashboard_snapshot"]()
    assert snapshot["tracker_equity"] == 201.1212
    assert snapshot["peak_equity"] == 201.5609
    assert snapshot["drawdown_display"] == "0.2200%"
    rendered = "\n".join(ns["command_dashboard_lines"](snapshot))
    assert "Equity: +201.1212" in rendered
    assert "Peak Equity: +201.5609" in rendered
    assert "Drawdown: 0.2200%" in rendered


def test_asset_pnl_matches_authoritative_asset_category_state():
    ns = _load_command_dashboard_collect_namespace()
    snapshot = ns["collect_command_dashboard_snapshot"]()
    rows = ns["aggregate_pnl_by_asset_category"](
        realized_pnl_maps=ns["current_realized_pnl_maps_by_asset_category"](),
        positions=[pos for pos in ns["mtm_engine"].positions if not pos.get("forced_exit")],
    )
    expected = {str(row["asset_category"]): row["total_pnl"] for row in rows}
    assert snapshot["pnl_by_asset"] == expected
    rendered = "\n".join(ns["command_dashboard_lines"](snapshot))
    assert f"Crypto P&L: {expected['CRYPTO']:+.4f}" in rendered
    assert f"FX P&L: {expected['FX']:+.4f}" in rendered


def test_live_execution_status_remains_no_in_paper_mode():
    ns = _load_command_dashboard_collect_namespace()
    snapshot = ns["collect_command_dashboard_snapshot"]()
    rendered = "\n".join(ns["command_dashboard_lines"](snapshot))
    assert snapshot["live_execute"] == "NO"
    assert snapshot["mode"] == "paper"
    assert "Live Execution: NO" in rendered
    assert "MODE: PAPER" in rendered
    assert "EXECUTION: PAPER ONLY" in rendered
    assert "Broker Execution: DISABLED" in rendered


def test_missing_safety_gates_render_unknown_not_green():
    ns = _load_command_dashboard_collect_namespace()
    lines = ns["command_dashboard_lines"]({})
    rendered = "\n".join(lines)
    assert "Unified Trade Gate: UNKNOWN" in rendered
    assert "Margin Gate: UNKNOWN" in rendered
    assert "Margin State: UNKNOWN" in rendered
    assert "Kill Switch: UNKNOWN" in rendered
    assert "Unified Trade Gate: GREEN" not in rendered
    assert "Margin Gate: GREEN" not in rendered


def test_display_layer_cannot_mutate_trading_state():
    ns = _load_command_dashboard_collect_namespace()
    original_positions = copy.deepcopy(ns["mtm_engine"].positions)
    original_crypto = dict(ns["crypto_pnl"])
    original_fx = dict(ns["fx_pnl"])
    original_armed = ns["BROKER_EXECUTION_ARMED"]
    original_tracker_equity = ns["pnl_tracker"].current_equity
    snapshot = ns["collect_command_dashboard_snapshot"]()
    snapshot_copy = copy.deepcopy(snapshot)
    ns["command_dashboard_lines"](snapshot)
    assert snapshot == snapshot_copy
    assert ns["mtm_engine"].positions == original_positions
    assert ns["crypto_pnl"] == original_crypto
    assert ns["fx_pnl"] == original_fx
    assert ns["BROKER_EXECUTION_ARMED"] is original_armed
    assert ns["pnl_tracker"].current_equity == original_tracker_equity


def test_verbose_trade_dashboard_summary_remains_available(tmp_path):
    ns = _load_render_helpers(tmp_path)
    ns["render_trade_dashboard_summary"](_cow_snapshot())
    rendered = "\n".join(ns["_output"])
    assert "CSS COMMAND DASHBOARD" in rendered
    assert "=== TRADE DASHBOARD SUMMARY ===" in rendered
    assert rendered.find("CSS COMMAND DASHBOARD") < rendered.find("=== TRADE DASHBOARD SUMMARY ===")
    assert "=== OPEN POSITIONS BY ASSET CLASS ===" in rendered
    assert "=== PNL BY ASSET CATEGORY ===" in rendered
    assert "=== END TRADE DASHBOARD SUMMARY ===" in rendered


def test_command_dashboard_and_collect_do_not_add_order_or_broker_paths():
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for name in (
        "collect_command_dashboard_snapshot",
        "command_dashboard_lines",
        "render_trade_dashboard_summary",
    ):
        func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        called = {
            node.func.id
            for node in ast.walk(func)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert called.isdisjoint(FORBIDDEN_DISPLAY_CALLS)


def test_dashboard_hotfix_does_not_change_broker_or_execution_authority():
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "origin/css-v1.0.1-maintenance"],
        cwd=PROJECT_ROOT,
        text=True,
    ).splitlines()
    blocked = [
        path
        for path in changed
        if any(path == prefix or path.startswith(prefix) for prefix in SAFETY_PATH_PREFIXES)
    ]
    assert blocked == []
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    collect = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "collect_command_dashboard_snapshot"
    )
    assigned = {
        target.id
        for node in ast.walk(collect)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "BROKER_EXECUTION_ARMED" not in assigned
    assert "SELECTED_BROKER_MODE" not in assigned
    assert "SELECTED_BROKER" not in assigned
