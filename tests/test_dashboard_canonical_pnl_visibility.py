import ast
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from engine.ledger import CANONICAL_PNL_SOURCE
from engine.ledger.ledger_models import PnLSnapshot
from engine.ledger.ledger_store import LedgerStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


def _load_canonical_pnl_dashboard_helpers():
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {
        "_format_canonical_pnl_dashboard_value",
        "canonical_pnl_dashboard_lines",
    }

    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    namespace = {"Any": Any}
    exec(compile(module, str(DASHBOARD_PATH), "exec"), namespace)
    return namespace


def _store_with_snapshot() -> LedgerStore:
    store = LedgerStore()
    store.add_pnl_snapshot(
        PnLSnapshot(
            as_of=datetime.now(timezone.utc),
            symbol="BTC-USD",
            currency="USD",
            realized_pnl=Decimal("50.0"),
            unrealized_pnl=Decimal("30.0"),
            company_id="COMPANY-1",
            branch_id="BRANCH-1",
            department_id="DEPT-1",
            user_id="USER-1",
            meta={"qty": "1", "avg_cost": "100"},
        )
    )
    return store


def test_dashboard_canonical_pnl_helper_reads_adapter_output():
    ns = _load_canonical_pnl_dashboard_helpers()

    lines = ns["canonical_pnl_dashboard_lines"](
        ledger_store=_store_with_snapshot(),
        starting_equity=Decimal("1000"),
        asset_class_by_symbol={"BTC-USD": "CRYPTO"},
        company_id="COMPANY-1",
        branch_id="BRANCH-1",
        department_id="DEPT-1",
        user_id="USER-1",
    )

    rendered = "\n".join(lines)
    assert "=== CANONICAL PNL DIAGNOSTIC ===" in rendered
    assert "Canonical PnL Status: AVAILABLE" in rendered
    assert f"Source: {CANONICAL_PNL_SOURCE}" in rendered
    assert "Canonical Realized PnL: +50.0000" in rendered
    assert "Canonical Unrealized PnL: +30.0000" in rendered
    assert "Canonical Net PnL: +80.0000" in rendered
    assert "Canonical Equity: +1080.0000" in rendered
    assert "=== END CANONICAL PNL DIAGNOSTIC ===" in rendered


def test_missing_canonical_snapshot_does_not_crash_dashboard_helper():
    ns = _load_canonical_pnl_dashboard_helpers()

    lines = ns["canonical_pnl_dashboard_lines"]()

    assert lines == [
        "=== CANONICAL PNL DIAGNOSTIC ===",
        "Canonical PnL Status: UNAVAILABLE",
        "Reason: canonical ledger snapshot unavailable",
        "=== END CANONICAL PNL DIAGNOSTIC ===",
    ]


def test_canonical_snapshot_output_compares_with_dashboard_summary_shape():
    ns = _load_canonical_pnl_dashboard_helpers()
    dashboard_summary = {
        "realized_pnl": 50.0,
        "unrealized_pnl": 30.0,
        "net_pnl": 80.0,
        "asset_realized_pnl": {"CRYPTO": 50.0},
        "asset_unrealized_pnl": {"CRYPTO": 30.0},
        "source": "LEGACY_POSITION_STATE",
    }
    canonical_summary = {
        "realized_pnl": 50.0,
        "unrealized_pnl": 30.0,
        "net_pnl": 80.0,
        "equity": 1080.0,
        "peak_equity": 1080.0,
        "current_drawdown": 0.0,
        "max_drawdown": 0.0,
        "asset_realized_pnl": {"CRYPTO": 50.0},
        "asset_unrealized_pnl": {"CRYPTO": 30.0},
        "open_positions": 1,
        "closed_positions": 0,
        "source": CANONICAL_PNL_SOURCE,
    }

    lines = ns["canonical_pnl_dashboard_lines"](
        dashboard_summary=dashboard_summary,
        canonical_summary=canonical_summary,
    )

    rendered = "\n".join(lines)
    assert "PnL Parity: MATCH" in rendered
    assert "Realized Diff: +0.0000" in rendered
    assert "Unrealized Diff: +0.0000" in rendered
    assert "Net Diff: +0.0000" in rendered
    assert f"Source: {CANONICAL_PNL_SOURCE}" in rendered


def test_existing_dashboard_summary_is_not_wired_to_canonical_helper():
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    render_func = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "render_trade_dashboard_summary"
    )

    calls = {
        node.func.id
        for node in ast.walk(render_func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }

    assert "canonical_pnl_dashboard_lines" not in calls
