from __future__ import annotations

import pytest

from backend.runtime.canonical_broker_runtime_state import OVERALL_FAIL_CLOSED, OVERALL_GREEN, STATUS_PASS, STATUS_UNAVAILABLE
from backend.runtime.canonical_broker_state_builder import build_canonical_broker_runtime_state
from backend.runtime.canonical_broker_state_registry import CLASS_SANDBOX, CLASS_TEST, classify_coinbase_environment
from backend.runtime.canonical_broker_state_validator import validate_canonical_broker_state
from backend.runtime.coinbase_authentication_trace import trace_coinbase_authentication
from backend.runtime.runtime_certification_snapshot import build_runtime_certification_snapshot
from backend.runtime.startup_summary import STARTUP_SUMMARY_FIELDS, build_live_startup_summary, format_live_startup_summary
from dashboard.runtime.frontend_contract import build_frontend_payload


def _runtime_success() -> dict:
    return {
        "selected_broker": "COINBASE",
        "broker_mode": "live",
        "credential_status": "PRESENT",
        "broker_authenticated": True,
        "broker_connected": True,
        "account_loaded": True,
        "balances_loaded": True,
        "buying_power": 25.0,
        "margin_available": 25.0,
        "market_data_status": "PASS",
        "products_loaded": 5,
        "account_equity": 25.0,
        "portfolio_loaded": True,
        "order_submission_status": "DISABLED",
        "execution_scope": "READ_ONLY",
        "live_micro_pilot_state": "DISARMED",
    }


def test_phase166b_env_trace_classifies_consumer_purpose_and_live_contamination() -> None:
    evidence = classify_coinbase_environment(
        {
            "COINBASE_TEST_ORDER_USD": "1.00",
            "COINBASE_SANDBOX_URL": "https://sandbox.coinbase.example",
            "COINBASE_LEGACY_EXECUTION_ENABLED": "true",
            "COINBASE_MAX_LIVE_ORDER_USD": "1.00",
            "COINBASE_CDP_KEY_NAME": "redacted",
        },
        mode="live",
    )
    by_name = {item["variable_name"]: item for item in evidence["findings"]}

    assert evidence["status"] == "FAIL"
    assert set(evidence["contamination_keys"]) == {
        "COINBASE_LEGACY_EXECUTION_ENABLED",
        "COINBASE_SANDBOX_URL",
        "COINBASE_TEST_ORDER_USD",
    }
    assert by_name["COINBASE_TEST_ORDER_USD"]["classification"] == CLASS_TEST
    assert by_name["COINBASE_SANDBOX_URL"]["classification"] == CLASS_SANDBOX
    assert by_name["COINBASE_TEST_ORDER_USD"]["consumer"]
    assert by_name["COINBASE_TEST_ORDER_USD"]["purpose"]
    assert by_name["COINBASE_TEST_ORDER_USD"]["value_redacted"] is True
    assert by_name["COINBASE_MAX_LIVE_ORDER_USD"]["severity"] == "WARNING"


@pytest.mark.parametrize(
    ("message", "expected_code"),
    [
        ("unauthorized 401", "COINBASE_HTTP_401"),
        ("forbidden 403", "COINBASE_HTTP_403"),
        ("not found 404", "COINBASE_HTTP_404"),
        ("request timeout", "COINBASE_TIMEOUT"),
        ("DNS name resolution failed", "COINBASE_DNS_ERROR"),
        ("TLS certificate verify failed", "COINBASE_TLS_ERROR"),
        ("clock skew too large", "COINBASE_CLOCK_SKEW"),
        ("invalid JWT signature", "COINBASE_INVALID_JWT"),
        ("expired JWT token", "COINBASE_EXPIRED_JWT"),
        ("bad key format", "COINBASE_BAD_KEY"),
        ("permission denied", "COINBASE_PERMISSION_DENIED"),
        ("portfolio unavailable", "COINBASE_PORTFOLIO_UNAVAILABLE"),
        ("account unavailable", "COINBASE_ACCOUNT_UNAVAILABLE"),
        ("balance unavailable", "COINBASE_BALANCES_UNAVAILABLE"),
        ("market-data-only credentials", "COINBASE_MARKET_DATA_ONLY"),
        ("broker unavailable", "COINBASE_BROKER_UNAVAILABLE"),
    ],
)
def test_phase166b_auth_trace_preserves_distinct_failure_evidence(message: str, expected_code: str) -> None:
    class FailingAdapter:
        def get_server_time(self):
            raise RuntimeError(message)

    trace = trace_coinbase_authentication(FailingAdapter(), env={}, mode="live")

    assert trace["authentication"] == "FAIL"
    assert trace["coinbase_error_code"] == expected_code
    assert trace["execution_allowed"] is False
    assert trace["live_trading_blocked"] is True
    assert trace["broker_execution_armed"] is False
    assert trace["advisory_only"] is True


def test_phase166b_account_evidence_is_single_authoritative_object() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "account_type": "SPOT"},
    )

    assert state.overall_status == OVERALL_GREEN
    assert state.account_evidence == {
        "authenticated": True,
        "connected": True,
        "account_loaded": True,
        "balances_loaded": True,
        "buying_power_loaded": True,
        "margin_loaded": True,
        "products_loaded": True,
        "market_data_loaded": True,
        "equity_loaded": True,
        "account_type": "SPOT",
        "portfolio_loaded": True,
    }


def test_phase166b_balance_failure_forces_dependent_live_account_fields_unavailable() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "balances_loaded": False, "buying_power": 25.0, "margin_available": 25.0},
    )

    assert state.balance_status == STATUS_UNAVAILABLE
    assert state.buying_power_status == STATUS_UNAVAILABLE
    assert state.margin_status == STATUS_UNAVAILABLE
    assert state.account_evidence["balances_loaded"] is False
    assert state.account_evidence["buying_power_loaded"] is False
    assert state.account_evidence["margin_loaded"] is False
    assert state.account_evidence["equity_loaded"] is False


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"credential_status": "MISSING", "broker_authenticated": True}, "credentials_missing_but_authentication_pass"),
        ({"broker_authenticated": False, "broker_connected": True}, "authentication_failed_but_connection_ready"),
        ({"authentication": "FAIL", "account_status": "PASS"}, "authentication_failed_but_account_ready"),
        ({"balance_status": "UNAVAILABLE", "buying_power_status": "PASS"}, "balance_unavailable_but_buying_power_ready"),
        ({"balance_status": "UNAVAILABLE", "margin_status": "PASS"}, "balance_unavailable_but_margin_ready"),
        ({"order_submission_status": "ENABLED", "execution_scope": "READ_ONLY"}, "order_submission_enabled_in_read_only_scope"),
    ],
)
def test_phase166b_contradictions_fail_closed(payload: dict, reason: str) -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), **payload},
        margin_snapshot={"buying_power": 25.0, "margin_available": 25.0},
    )

    assert state.overall_status == OVERALL_FAIL_CLOSED
    assert reason in state.contradiction_reasons
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False
    assert validate_canonical_broker_state(state)["overall_status"] == OVERALL_FAIL_CLOSED


def test_phase166b_synthetic_live_margin_is_rejected() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "balances_loaded": False},
        margin_snapshot={"margin_source": "SIMULATED", "buying_power": 1000.0, "margin_available": 1000.0},
    )

    assert state.overall_status == OVERALL_FAIL_CLOSED
    assert "positive_simulated_live_margin" in state.contradiction_reasons


def test_phase166b_startup_output_uses_only_required_canonical_fields() -> None:
    summary = build_live_startup_summary(_runtime_success())
    lines = format_live_startup_summary(summary)
    labels = tuple(line.split(":", 1)[0] for line in lines[1:-1])

    assert labels == STARTUP_SUMMARY_FIELDS
    assert "State Hash" in summary
    assert summary["execution_allowed"] is False
    assert summary["live_trading_blocked"] is True
    assert summary["broker_execution_armed"] is False


def test_phase166b_frontend_and_runtime_certification_reuse_canonical_snapshot() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
        timestamp="2026-07-14T00:00:00+00:00",
    )
    frontend = build_frontend_payload({"broker_summary": {**_runtime_success(), "canonical_broker_runtime_state": state.to_dict()}})
    broker_section = frontend["sections"]["broker"]
    snapshot = build_runtime_certification_snapshot(
        "coinbase",
        mode="live",
        cycle_id="phase166b",
        phase156b={
            "broker": "COINBASE",
            "authentication": "PASS",
            "account": "PASS",
            "balances": "PASS",
            "market_data": "PASS",
            "products": "PASS",
            "certification": "GREEN",
            "products_loaded": 5,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        },
        phase156c={"health": "GREEN"},
    )

    assert broker_section["canonical_broker_runtime_state"]["state_hash"] == state.to_dict()["state_hash"]
    assert broker_section["canonical_account_evidence"] == state.to_dict()["account_evidence"]
    assert snapshot["canonical_broker_runtime_state"]["account_evidence"]["authenticated"] is True
    assert broker_section["execution_allowed"] is False
    assert snapshot["execution_allowed"] is False
