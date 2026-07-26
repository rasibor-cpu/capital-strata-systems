import copy

from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload, build_websocket_delta
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads


def _payload(account_payload):
    state = DashboardHydrationCoordinator().hydrate(account_payload=account_payload)
    return build_frontend_payload(state)["sections"]["account_summary"]


def test_account_hydration_preserves_unavailable_values_without_false_zero():
    account = _payload({"cash_balance": None, "total_equity": "", "currency": None})

    assert account["cash_balance"] is None
    assert account["total_equity"] is None
    assert account["currency"] == "UNAVAILABLE"
    assert account["availability_state"] == "UNAVAILABLE"
    assert account["cash_balance_availability"] == "UNAVAILABLE"
    assert account["total_equity_availability"] == "UNAVAILABLE"
    assert account["broker_balance_summary"]["execution_allowed"] is False
    assert account["broker_balance_summary"]["advisory_only"] is True


def test_account_hydration_keeps_valid_zero_and_numeric_strings_available():
    account = _payload(
        {
            "cash_balance": "0",
            "total_equity": "1250.50",
            "buying_power": 25,
            "currency": "usd",
        }
    )

    assert account["cash_balance"] == 0.0
    assert account["cash_balance_availability"] == "AVAILABLE"
    assert account["total_equity"] == 1250.5
    assert account["total_equity_availability"] == "AVAILABLE"
    assert account["buying_power"] == 25.0
    assert account["currency"] == "USD"


def test_account_hydration_rejects_invalid_and_non_finite_values():
    for value in ("not-a-number", float("inf"), float("-inf")):
        account = _payload({"cash_balance": value, "currency": "USD"})
        assert account["cash_balance"] is None
        assert account["cash_balance_availability"] == "UNAVAILABLE"


def test_account_hydration_allows_negative_pnl_without_blocking_render():
    account = _payload({"realized_pnl": "-12.5", "unrealized_pnl": -7.25, "currency": "USD"})

    summary = account["broker_balance_summary"]["account_summary"]
    assert summary["realized_pnl"]["value"] == -12.5
    assert summary["unrealized_pnl"]["value"] == -7.25
    assert account["broker_balance_summary"]["execution_allowed"] is False


def test_websocket_delta_ignores_broker_timestamp_only_volatility():
    previous = build_frontend_payload(DashboardHydrationCoordinator().hydrate(**build_smoke_payloads()))
    current = copy.deepcopy(previous)
    current["sections"]["broker"]["broker_operational_status"]["selected"]["operation_result"][
        "correlation_id"
    ] = "different"
    current["sections"]["broker"]["broker_operational_status"]["selected"]["operation_result"][
        "received_at"
    ] = "2099-01-01T00:00:00Z"

    delta = build_websocket_delta(previous, current, sections=("broker",))

    assert delta["changed_sections"] == []


def test_websocket_delta_reports_meaningful_broker_change():
    previous = build_frontend_payload(DashboardHydrationCoordinator().hydrate(**build_smoke_payloads()))
    current = copy.deepcopy(previous)
    current["sections"]["broker"]["connection_status"] = "FAIL"

    delta = build_websocket_delta(previous, current, sections=("broker",))

    assert delta["changed_sections"] == ["broker"]


def test_websocket_delta_reports_execution_only_change():
    previous = build_frontend_payload(DashboardHydrationCoordinator().hydrate(**build_smoke_payloads()))
    payloads = build_smoke_payloads()
    payloads["execution_payload"]["accepted_trade_count"] = 3
    payloads["execution_payload"]["last_execution_event"] = "Performance smoke execution delta"
    current = build_frontend_payload(DashboardHydrationCoordinator().hydrate(**payloads))

    delta = build_websocket_delta(
        previous,
        current,
        sections=("execution", "risk", "positions", "broker"),
    )

    assert delta["changed_sections"] == ["execution"]
