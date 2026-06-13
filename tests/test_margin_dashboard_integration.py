import ast
from pathlib import Path
from typing import Any

from engine.risk.broker_margin_contract import BrokerMarginSnapshot


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


class FakeMarginAdapter:
    def __init__(
        self,
        *,
        broker_name: str = "TEST",
        account_id: str = "TEST-ACCOUNT",
        margin_source: str = "SIMULATED",
        required_margin: float = 1000.0,
        available_margin: float = 10000.0,
        free_margin: float = 9000.0,
    ):
        self.broker_name = broker_name
        self.account_id = account_id
        self.margin_source = margin_source
        self.required_margin = required_margin
        self.available_margin = available_margin
        self.free_margin = free_margin
        self.execution_methods_called = []

    def get_margin_snapshot(self):
        return BrokerMarginSnapshot(
            broker_name=self.broker_name,
            account_id=self.account_id,
            required_margin=self.required_margin,
            available_margin=self.available_margin,
            free_margin=self.free_margin,
            margin_utilization_pct=0.0,
            margin_source=self.margin_source,
            timestamp="2026-06-12T00:00:00+00:00",
        )

    def place_order(self, *args, **kwargs):
        self.execution_methods_called.append("place_order")
        raise AssertionError("place_order must not be called by margin dashboard")

    def place_market_buy(self, *args, **kwargs):
        self.execution_methods_called.append("place_market_buy")
        raise AssertionError("place_market_buy must not be called by margin dashboard")

    def close_trade(self, *args, **kwargs):
        self.execution_methods_called.append("close_trade")
        raise AssertionError("close_trade must not be called by margin dashboard")


class FailingMarginAdapter:
    def get_margin_snapshot(self):
        raise RuntimeError("margin unavailable")


def _load_margin_dashboard_helpers():
    source = DASHBOARD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {
        "_format_margin_dashboard_value",
        "_margin_dashboard_mode_is_live",
        "_margin_dashboard_adapter_for_context",
        "margin_dashboard_lines",
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


def test_margin_dashboard_lines_render_in_simulated_mode():
    ns = _load_margin_dashboard_helpers()

    lines = ns["margin_dashboard_lines"](
        selected_broker="NONE",
        selected_broker_mode="paper",
    )

    rendered = "\n".join(lines)
    assert "=== MARGIN DASHBOARD ===" in rendered
    assert "Margin Source: SIMULATED" in rendered
    assert "Broker Mode: PAPER" in rendered
    assert "Required Margin:" in rendered
    assert "Available Margin:" in rendered
    assert "Free Margin:" in rendered
    assert "Utilization %:" in rendered
    assert "=== END MARGIN DASHBOARD ===" in rendered


def test_oanda_broker_selection_renders_oanda_margin_path():
    ns = _load_margin_dashboard_helpers()

    lines = ns["margin_dashboard_lines"](
        selected_broker="OANDA",
        selected_broker_mode="paper",
    )

    rendered = "\n".join(lines)
    assert "Broker: OANDA" in rendered
    assert "Margin Source: SIMULATED" in rendered


def test_coinbase_broker_selection_renders_coinbase_margin_path():
    ns = _load_margin_dashboard_helpers()

    lines = ns["margin_dashboard_lines"](
        selected_broker="COINBASE",
        selected_broker_mode="paper",
    )

    rendered = "\n".join(lines)
    assert "Broker: COINBASE" in rendered
    assert "Margin Source: SIMULATED" in rendered


def test_unsupported_broker_falls_back_safely():
    ns = _load_margin_dashboard_helpers()

    lines = ns["margin_dashboard_lines"](
        selected_broker="UNSUPPORTED",
        selected_broker_mode="paper",
    )

    rendered = "\n".join(lines)
    assert "Broker: UNSUPPORTED" in rendered
    assert "Margin Source: SIMULATED" in rendered
    assert "Margin Status: UNAVAILABLE" not in rendered


def test_margin_gate_decision_appears_in_output():
    ns = _load_margin_dashboard_helpers()

    lines = ns["margin_dashboard_lines"](
        selected_broker="NONE",
        selected_broker_mode="paper",
    )

    rendered = "\n".join(lines)
    assert "Trade Gate Decision:" in rendered
    assert "Trade Gate Allowed:" in rendered
    assert "Trade Gate Reason:" in rendered


def test_dashboard_error_path_does_not_raise():
    ns = _load_margin_dashboard_helpers()
    ns["_margin_dashboard_adapter_for_context"] = lambda *_args, **_kwargs: (
        FailingMarginAdapter(),
        "BROKEN",
    )

    lines = ns["margin_dashboard_lines"](
        selected_broker="OANDA",
        selected_broker_mode="live",
    )

    assert lines == [
        "=== MARGIN DASHBOARD ===",
        "Margin Status: UNAVAILABLE",
        "Reason: margin unavailable",
        "=== END MARGIN DASHBOARD ===",
    ]


def test_no_trade_execution_functions_are_called():
    ns = _load_margin_dashboard_helpers()
    adapter = FakeMarginAdapter(
        broker_name="COINBASE",
        margin_source="LIVE",
        required_margin=1000.0,
        available_margin=10000.0,
        free_margin=9000.0,
    )
    ns["_margin_dashboard_adapter_for_context"] = lambda *_args, **_kwargs: (
        adapter,
        "COINBASE",
    )

    lines = ns["margin_dashboard_lines"](
        selected_broker="COINBASE",
        selected_broker_mode="live",
    )

    rendered = "\n".join(lines)
    assert "Trade Gate Decision:" in rendered
    assert adapter.execution_methods_called == []
