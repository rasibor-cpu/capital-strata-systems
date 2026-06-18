import ast
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


def _load_pnl_category_helpers():
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted_defs = {
        "current_realized_pnl_maps_by_asset_category",
        "normalize_asset_category",
        "_safe_dashboard_float",
        "aggregate_pnl_by_asset_category",
        "pnl_by_asset_category_dashboard_lines",
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted_defs
    ]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    namespace = {"Any": Any}
    exec(compile(module, str(DASHBOARD_PATH), "exec"), namespace)
    return namespace


def test_category_aggregation_combines_realized_unrealized_and_total() -> None:
    ns = _load_pnl_category_helpers()

    rows = ns["aggregate_pnl_by_asset_category"](
        realized_pnl_maps={
            "FX": {"EUR_USD": 10.0, "GBP_USD": -2.5},
            "CRYPTO": {"BTC-USD": 3.0},
        },
        positions=[
            {"asset_class": "FX", "floating": 1.5},
            {"asset_class": "CRYPTO", "unrealized_pnl": -0.5},
        ],
    )

    by_category = {row["asset_category"]: row for row in rows}
    assert by_category["FX"]["realized_pnl"] == 7.5
    assert by_category["FX"]["unrealized_pnl"] == 1.5
    assert by_category["FX"]["total_pnl"] == 9.0
    assert by_category["CRYPTO"]["realized_pnl"] == 3.0
    assert by_category["CRYPTO"]["unrealized_pnl"] == -0.5
    assert by_category["CRYPTO"]["total_pnl"] == 2.5


def test_empty_categories_render_without_crash() -> None:
    ns = _load_pnl_category_helpers()

    rows = ns["aggregate_pnl_by_asset_category"](
        realized_pnl_maps={},
        positions=[],
    )
    lines = ns["pnl_by_asset_category_dashboard_lines"](rows)

    assert rows == []
    assert "No asset-category PnL available." in lines
    assert lines[0] == "=== PNL BY ASSET CATEGORY ==="


def test_unknown_categories_are_handled_safely() -> None:
    ns = _load_pnl_category_helpers()

    rows = ns["aggregate_pnl_by_asset_category"](
        realized_pnl_maps={"": {"UNKNOWN-SYM": 2.0}},
        positions=[{"asset_class": "", "floating": 1.0}],
    )

    assert rows == [
        {
            "asset_category": "UNKNOWN",
            "open_positions": 1,
            "realized_pnl": 2.0,
            "unrealized_pnl": 1.0,
            "total_pnl": 3.0,
        }
    ]


def test_dashboard_rendering_receives_aggregated_values() -> None:
    ns = _load_pnl_category_helpers()

    rows = [
        {
            "asset_category": "FX",
            "open_positions": 2,
            "realized_pnl": 7.5,
            "unrealized_pnl": 1.5,
            "total_pnl": 9.0,
        }
    ]
    rendered = "\n".join(ns["pnl_by_asset_category_dashboard_lines"](rows))

    assert "FX           Open 2" in rendered
    assert "Realized +7.5000" in rendered
    assert "Unrealized +1.5000" in rendered
    assert "Total +9.0000" in rendered


def test_future_categories_are_supported_without_ui_changes() -> None:
    ns = _load_pnl_category_helpers()

    rows = ns["aggregate_pnl_by_asset_category"](
        realized_pnl_maps={
            "EQUITIES": {"AAPL": 4.0},
            "ETFS": {"SPY": 1.25},
            "COMMODITIES": {"GC": -0.5},
        },
        positions=[
            {"asset_class": "FIXED_INCOME", "floating": 0.75},
            {"asset_class": "ETFS", "floating": 2.0},
        ],
    )
    rendered = "\n".join(ns["pnl_by_asset_category_dashboard_lines"](rows))

    assert "EQUITIES" in rendered
    assert "ETFS" in rendered
    assert "COMMODITIES" in rendered
    assert "FIXED_INCOME" in rendered
