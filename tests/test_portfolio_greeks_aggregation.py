import ast
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


def _load_dashboard_greeks_helpers():
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted_assigns = {
        "OPTION_GREEK_FIELDS",
        "VALID_GREEKS_SOURCES",
        "PORTFOLIO_GREEK_FIELDS",
    }
    wanted_defs = {
        "default_option_greeks",
        "normalize_option_greeks",
        "portfolio_greeks_from_positions",
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

    namespace = {"Any": Any}
    exec(compile(module, str(DASHBOARD_PATH), "exec"), namespace)
    return namespace


def test_empty_positions_returns_unavailable_none_portfolio_greeks():
    ns = _load_dashboard_greeks_helpers()

    assert ns["portfolio_greeks_from_positions"]([]) == {
        "net_delta": None,
        "net_gamma": None,
        "net_theta": None,
        "net_vega": None,
        "net_rho": None,
        "greeks_source": "UNAVAILABLE",
        "greeks_status": "UNAVAILABLE",
        "greeks_reason": "NO_OPTION_GREEKS_AVAILABLE",
    }


def test_non_options_positions_are_ignored():
    ns = _load_dashboard_greeks_helpers()
    positions = [
        {"asset_class": "CRYPTO", "delta": 10.0, "greeks_source": "BROKER"},
        {"asset_class": "FX", "gamma": 10.0, "greeks_source": "BROKER"},
        {"asset_class": "FUTURES", "theta": 10.0, "greeks_source": "BROKER"},
    ]

    result = ns["portfolio_greeks_from_positions"](positions)

    assert result["net_delta"] is None
    assert result["net_gamma"] is None
    assert result["net_theta"] is None
    assert result["net_vega"] is None
    assert result["net_rho"] is None
    assert result["greeks_source"] == "UNAVAILABLE"
    assert result["greeks_status"] == "UNAVAILABLE"


def test_options_positions_with_numeric_greeks_aggregate_correctly():
    ns = _load_dashboard_greeks_helpers()
    positions = [
        {
            "asset_class": "OPTIONS",
            "delta": 0.50,
            "gamma": 0.10,
            "theta": -0.20,
            "vega": 1.25,
            "rho": 0.05,
            "greeks_source": "MARKET_DATA",
        },
        {
            "asset_class": "OPTIONS",
            "delta": -0.15,
            "gamma": 0.03,
            "theta": -0.05,
            "vega": 0.75,
            "rho": 0.02,
            "greeks_source": "MARKET_DATA",
        },
    ]

    result = ns["portfolio_greeks_from_positions"](positions)

    assert result["net_delta"] == pytest.approx(0.35)
    assert result["net_gamma"] == pytest.approx(0.13)
    assert result["net_theta"] == pytest.approx(-0.25)
    assert result["net_vega"] == pytest.approx(2.0)
    assert result["net_rho"] == pytest.approx(0.07)
    assert result["greeks_status"] == "RESOLVED"


def test_none_greeks_are_ignored():
    ns = _load_dashboard_greeks_helpers()
    positions = [
        {
            "asset_class": "OPTIONS",
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
            "rho": None,
            "greeks_source": "BROKER",
        },
        {
            "asset_class": "OPTIONS",
            "delta": 0.20,
            "gamma": None,
            "theta": -0.04,
            "vega": None,
            "rho": None,
            "greeks_source": "BROKER",
        },
    ]

    result = ns["portfolio_greeks_from_positions"](positions)

    assert result["net_delta"] == 0.20
    assert result["net_gamma"] is None
    assert result["net_theta"] == -0.04
    assert result["net_vega"] is None
    assert result["net_rho"] is None


def test_forced_exit_options_positions_are_ignored():
    ns = _load_dashboard_greeks_helpers()
    positions = [
        {
            "asset_class": "OPTIONS",
            "forced_exit": True,
            "delta": 9.0,
            "gamma": 9.0,
            "greeks_source": "BROKER",
        }
    ]

    result = ns["portfolio_greeks_from_positions"](positions)

    assert result["net_delta"] is None
    assert result["net_gamma"] is None
    assert result["greeks_source"] == "UNAVAILABLE"
    assert result["greeks_status"] == "UNAVAILABLE"


def test_mixed_valid_sources_produce_mixed_source():
    ns = _load_dashboard_greeks_helpers()
    positions = [
        {"asset_class": "OPTIONS", "delta": 0.10, "greeks_source": "BROKER"},
        {"asset_class": "OPTIONS", "delta": 0.15, "greeks_source": "MARKET_DATA"},
    ]

    result = ns["portfolio_greeks_from_positions"](positions)

    assert result["net_delta"] == pytest.approx(0.25)
    assert result["greeks_source"] == "MIXED"
    assert result["greeks_status"] == "PARTIAL"


def test_single_valid_source_is_preserved():
    ns = _load_dashboard_greeks_helpers()
    positions = [
        {"asset_class": "OPTIONS", "delta": 0.10, "greeks_source": "BLACK_SCHOLES"},
        {"asset_class": "OPTIONS", "gamma": 0.02, "greeks_source": "BLACK_SCHOLES"},
    ]

    result = ns["portfolio_greeks_from_positions"](positions)

    assert result["net_delta"] == 0.10
    assert result["net_gamma"] == 0.02
    assert result["greeks_source"] == "BLACK_SCHOLES"
    assert result["greeks_status"] == "RESOLVED"


def test_invalid_or_missing_source_normalizes_safely():
    ns = _load_dashboard_greeks_helpers()
    positions = [
        {"asset_class": "OPTIONS", "delta": 0.10, "greeks_source": "BAD_SOURCE"},
        {"asset_class": "OPTIONS", "gamma": 0.02},
    ]

    result = ns["portfolio_greeks_from_positions"](positions)

    assert result["net_delta"] == 0.10
    assert result["net_gamma"] == 0.02
    assert result["greeks_source"] == "UNAVAILABLE"
    assert result["greeks_status"] == "PARTIAL"
