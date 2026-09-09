from datetime import datetime, timezone
from decimal import Decimal

from backend.brokers.questrade_readonly import parse_questrade_readonly_response
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.mission_control_state import (
    CURRENT,
    STALE,
    UNAVAILABLE,
    build_mission_control_state,
)


def _response(**overrides):
    payload = {
        "status": "AVAILABLE",
        "account": {"accountId": "QT-1", "currency": "CAD"},
        "balances": {"cash": "0", "equity": "0", "buying_power": "12.50"},
        "positions": [],
        "activities": [],
        "timestamp": "2026-09-09T12:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def test_questrade_parser_preserves_explicit_zero_and_is_read_only():
    response = _response()
    parsed = parse_questrade_readonly_response(response)

    assert parsed["balances"]["cash"] == "0"
    assert parsed["positions"] == []
    assert parsed["read_only"] is True
    assert response["balances"]["cash"] == "0"


def test_missing_balance_is_unavailable_not_zero():
    parsed = parse_questrade_readonly_response(_response(balances=None))

    assert parsed["balances"] is None
    assert "BALANCE_UNAVAILABLE" in parsed["reason_codes"]


def test_auth_and_expired_token_fail_closed():
    assert "AUTHENTICATION_REQUIRED" in parse_questrade_readonly_response(
        {"error": "401"}
    )["reason_codes"]
    assert "TOKEN_EXPIRED" in parse_questrade_readonly_response(
        {"error": "TOKEN_EXPIRED"}
    )["reason_codes"]


def test_live_mode_without_explicit_provenance_is_not_real_broker():
    state = build_mission_control_state(
        {
            "broker_name": "QUESTRADE",
            "account_mode": "LIVE",
            "response": _response(),
        }
    )

    assert state.capital_provenance == "UNKNOWN"
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.advisory_only is True


def test_simulated_account_is_explicitly_labeled():
    state = build_mission_control_state(
        {
            "broker_name": "QUESTRADE",
            "account_mode": "PAPER",
            "capital_provenance": "SIMULATED_PAPER",
            "response": _response(),
        }
    )

    assert state.capital_provenance == "SIMULATED_PAPER"
    assert "SIMULATED_ACCOUNT" in state.state_reason_codes


def test_freshness_is_current_stale_or_unavailable():
    current = build_mission_control_state({"status": "AVAILABLE", "timestamp": datetime.now(timezone.utc).isoformat(), "balances": {}, "positions": []})
    stale = build_mission_control_state({"status": "AVAILABLE", "timestamp": "2020-01-01T00:00:00+00:00", "balances": {}, "positions": []})
    unavailable = build_mission_control_state({"status": "UNAVAILABLE"})

    assert current.data_freshness == CURRENT
    assert stale.data_freshness == STALE
    assert unavailable.data_freshness == UNAVAILABLE
    assert "DATA_STALE" in stale.state_reason_codes


def test_decimal_values_and_pnl_are_not_float_coerced():
    state = build_mission_control_state(
        {
            "status": "AVAILABLE",
            "timestamp": "2026-09-09T12:00:00+00:00",
            "balances": {"cash": "10.01", "equity": "12.34"},
            "positions": [{"symbol": "ABC", "quantity": "2"}],
            "session_realized_pnl": "1.10",
            "session_unrealized_pnl": "2.20",
            "session_total_pnl": "3.30",
        }
    )

    assert state.cash == Decimal("10.01")
    assert state.session_total_pnl == Decimal("3.30")
    assert state.as_dict()["cash"] == "10.01"


def test_reconciliation_status_is_exposed_without_overriding_broker_values():
    state = build_mission_control_state(
        {
            "broker_name": "QUESTRADE",
            "status": "AVAILABLE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "balances": {"cash": "10.00", "equity": "10.00"},
            "positions": [],
        },
        local_account={"cash_balance": "20.00", "total_equity": "20.00", "buying_power": "20.00"},
        local_positions=[],
    )

    assert state.reconciliation_status == "MISMATCH"
    assert state.cash == Decimal("10.00")


def test_api_exposes_read_only_mission_control_routes():
    app = create_app(lambda: DashboardState())
    paths = set(app.openapi()["paths"])

    assert "/api/v1/mission-control" in paths
    assert "/api/v1/broker-state" in paths
    assert "/api/v1/questrade/account-summary" in paths
    assert not any(path.startswith("/api/v1/questrade/") and path != "/api/v1/questrade/account-summary" for path in paths)
