import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


def _load_dashboard_display_helpers(tmp_path=None, positions=None):
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted_assigns = {
        "OPTION_GREEK_FIELDS",
        "VALID_GREEKS_SOURCES",
        "PORTFOLIO_GREEK_FIELDS",
    }
    wanted_defs = {
        "portfolio_greeks_from_positions",
        "format_greeks_dashboard_value",
        "option_position_greeks_dashboard_lines",
        "portfolio_greeks_dashboard_lines",
        "_format_margin_dashboard_value",
        "_margin_dashboard_mode_is_live",
        "_margin_dashboard_adapter_for_context",
        "margin_dashboard_lines",
        "render_trade_dashboard_summary",
    }

    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            target_names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if target_names & wanted_assigns:
                nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_defs:
            nodes.append(node)

    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    output = []
    namespace = {
        "Any": Any,
        "print": lambda *args, **_kwargs: output.append(" ".join(str(arg) for arg in args)),
        "mtm_engine": SimpleNamespace(positions=positions or []),
        "crypto_pnl": {},
        "fx_pnl": {},
        "futures_pnl": {},
        "options_pnl": {},
        "MAX_PAPER_OPEN_POSITIONS": 10,
        "ENGINE_MODE": "TEST",
        "SELECTED_BROKER": "NONE",
        "SELECTED_BROKER_MODE": "paper",
        "cycle": 3,
        "last_trade": "NONE",
        "CLOSED_TRADE_LEDGER_PATH": (tmp_path / "closed_trades.jsonl") if tmp_path else Path("closed_trades.jsonl"),
    }
    exec(compile(module, str(DASHBOARD_PATH), "exec"), namespace)
    namespace["_output"] = output
    return namespace


def test_unknown_greeks_render_as_unknown(tmp_path):
    ns = _load_dashboard_display_helpers(tmp_path)
    lines = ns["option_position_greeks_dashboard_lines"](
        [{"asset_class": "OPTIONS", "position_id": "POS-1", "symbol": "SPY-C"}]
    )

    rendered = "\n".join(lines)
    assert "Delta UNKNOWN" in rendered
    assert "Gamma UNKNOWN" in rendered
    assert "Theta UNKNOWN" in rendered
    assert "Vega UNKNOWN" in rendered
    assert "Rho UNKNOWN" in rendered
    assert "Greeks Source UNKNOWN" in rendered
    assert "0.00" not in rendered


def test_numeric_greeks_render_correctly(tmp_path):
    ns = _load_dashboard_display_helpers(tmp_path)
    lines = ns["option_position_greeks_dashboard_lines"](
        [
            {
                "asset_class": "OPTIONS",
                "position_id": "POS-2",
                "symbol": "QQQ-C",
                "delta": 0.42,
                "gamma": 0.03,
                "theta": -0.02,
                "vega": 0.11,
                "rho": 0.01,
                "greeks_source": "MARKET_DATA",
            }
        ]
    )

    rendered = "\n".join(lines)
    assert "Delta 0.4200" in rendered
    assert "Gamma 0.0300" in rendered
    assert "Theta -0.0200" in rendered
    assert "Vega 0.1100" in rendered
    assert "Rho 0.0100" in rendered
    assert "Greeks Source MARKET_DATA" in rendered


def test_portfolio_greeks_render_correctly(tmp_path):
    ns = _load_dashboard_display_helpers(tmp_path)
    lines = ns["portfolio_greeks_dashboard_lines"](
        [
            {"asset_class": "OPTIONS", "delta": 0.40, "gamma": 0.10, "greeks_source": "BROKER"},
            {"asset_class": "OPTIONS", "delta": -0.15, "theta": -0.04, "greeks_source": "BROKER"},
        ]
    )

    rendered = "\n".join(lines)
    assert "Net Delta 0.2500" in rendered
    assert "Net Gamma 0.1000" in rendered
    assert "Net Theta -0.0400" in rendered
    assert "Net Vega UNKNOWN" in rendered
    assert "Net Rho UNKNOWN" in rendered
    assert "Greeks Source BROKER" in rendered


def test_non_options_positions_do_not_display_position_greeks(tmp_path):
    ns = _load_dashboard_display_helpers(tmp_path)
    lines = ns["option_position_greeks_dashboard_lines"](
        [{"asset_class": "CRYPTO", "position_id": "POS-3", "symbol": "BTC-USD", "delta": 99.0}]
    )

    rendered = "\n".join(lines)
    assert "No open OPTIONS positions." in rendered
    assert "BTC-USD" not in rendered
    assert "Delta 99.0000" not in rendered


def test_existing_dashboard_summary_behavior_remains_intact(tmp_path):
    ns = _load_dashboard_display_helpers(
        tmp_path,
        positions=[
            {
                "asset_class": "OPTIONS",
                "position_id": "POS-4",
                "symbol": "SPY-C",
                "floating": 1.0,
                "delta": 0.25,
                "greeks_source": "BROKER",
            }
        ],
    )

    ns["render_trade_dashboard_summary"]()
    rendered = "\n".join(ns["_output"])

    assert "=== TRADE DASHBOARD SUMMARY ===" in rendered
    assert "=== OPEN POSITIONS BY ASSET CLASS ===" in rendered
    assert "=== PNL BY ASSET CLASS ===" in rendered
    assert "Last Trade: NONE" in rendered
    assert "Closed Trade Ledger: NO" in rendered
    assert "=== OPTIONS POSITION GREEKS ===" in rendered
    assert "=== PORTFOLIO GREEKS ===" in rendered
