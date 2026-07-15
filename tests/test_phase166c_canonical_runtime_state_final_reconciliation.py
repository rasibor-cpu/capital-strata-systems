from __future__ import annotations

from backend.runtime.canonical_broker_runtime_state import OVERALL_FAIL_CLOSED, OVERALL_GREEN, STATUS_FAIL, STATUS_PASS, STATUS_UNAVAILABLE
from backend.runtime.canonical_broker_state_adapter import adapt_canonical_state_to_legacy_broker_payload
from backend.runtime.canonical_broker_state_builder import build_canonical_broker_runtime_state
from backend.runtime.runtime_certification_snapshot import build_runtime_certification_snapshot
from backend.runtime.startup_summary import build_live_startup_summary, format_live_startup_summary
from dashboard.runtime.frontend_contract import build_frontend_payload


def _runtime_success() -> dict:
    return {
        "selected_broker": "COINBASE",
        "broker_mode": "live",
        "credential_status": "PRESENT",
        "api_reachable": True,
        "broker_authenticated": True,
        "broker_connected": True,
        "account_loaded": True,
        "balances_loaded": True,
        "buying_power": 100.45,
        "margin_available": 100.45,
        "market_data_status": "PASS",
        "products_loaded": 7,
        "account_equity": 100.45,
        "portfolio_loaded": True,
        "order_submission_status": "DISABLED",
        "execution_scope": "READ_ONLY",
        "live_micro_pilot_state": "DISARMED",
    }


def test_phase166c_connection_model_separates_transport_from_authenticated_connection() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "broker_authenticated": False, "api_reachable": True, "broker_connected": True},
    )

    assert state.transport_status == STATUS_PASS
    assert state.authentication_status == STATUS_FAIL
    assert state.connection_status == STATUS_FAIL
    assert state.account_evidence["transport_reachable"] is True
    assert state.account_evidence["connected"] is False
    assert state.overall_status == OVERALL_FAIL_CLOSED
    assert "authentication_failed_but_connection_ready" in state.contradiction_reasons


def test_phase166c_balance_unavailable_blocks_margin_buying_power_and_equity_with_provenance() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "balances_loaded": False, "buying_power": 100.45, "margin_available": 100.45},
        margin_snapshot={"margin_source": "LIVE_UNAVAILABLE", "buying_power": 0.0, "margin_available": 0.0},
    )

    assert state.balance_status == STATUS_UNAVAILABLE
    assert state.buying_power_status == STATUS_UNAVAILABLE
    assert state.margin_status == STATUS_UNAVAILABLE
    assert state.account_evidence["buying_power_loaded"] is False
    assert state.account_evidence["margin_loaded"] is False
    assert state.account_evidence["equity_loaded"] is False
    assert state.status_provenance["balances"] == "UNAVAILABLE"
    assert state.status_provenance["margin"] == "UNAVAILABLE"
    assert state.failure_reason != "NONE"


def test_phase166c_cache_or_historical_margin_is_explicitly_provenanced() -> None:
    cached = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
        margin_snapshot={"margin_source": "CACHE", "buying_power": 100.45, "margin_available": 100.45},
    )
    historical = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
        margin_snapshot={"margin_source": "HISTORICAL", "buying_power": 100.45, "margin_available": 100.45},
    )

    assert cached.status_provenance["margin"] == "CACHE"
    assert cached.status_provenance["buying_power"] == "CACHE"
    assert historical.status_provenance["margin"] == "HISTORICAL"
    assert historical.status_provenance["buying_power"] == "HISTORICAL"


def test_phase166c_failure_reasons_are_structured() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={"selected_broker": "COINBASE", "broker_mode": "live", "credential_status": "PRESENT"},
        auth_trace={"authentication": "FAIL", "coinbase_error_code": "COINBASE_HTTP_401", "http_status": 401},
    )

    assert state.failure_reason == "HTTP_401"
    assert state.http_status == 401
    assert state.overall_status == OVERALL_FAIL_CLOSED


def test_phase166c_startup_frontend_and_certification_share_hash_and_provenance() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
        timestamp="2026-07-15T00:00:00+00:00",
    )
    startup = build_live_startup_summary({**_runtime_success(), "canonical_broker_runtime_state": state.to_dict()})
    frontend = build_frontend_payload({"broker_summary": {**_runtime_success(), "canonical_broker_runtime_state": state.to_dict()}})
    snapshot = build_runtime_certification_snapshot(
        "coinbase",
        mode="live",
        cycle_id="phase166c",
        phase156b={
            "broker": "COINBASE",
            "authentication": "PASS",
            "account": "PASS",
            "balances": "PASS",
            "market_data": "PASS",
            "products": "PASS",
            "certification": "GREEN",
            "products_loaded": 7,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        },
        phase156c={"health": "GREEN"},
    )
    formatted = "\n".join(format_live_startup_summary(startup))

    assert "Provenance:" in formatted
    assert startup["startup_diagnostics"]["state_hash"] == startup["startup_diagnostics"]["canonical_broker_runtime_state"]["state_hash"]
    assert frontend["sections"]["broker"]["state_hash"] == state.to_dict()["state_hash"]
    assert frontend["sections"]["broker"]["status_provenance"] == state.to_dict()["status_provenance"]
    assert snapshot["state_hash"] == snapshot["canonical_broker_runtime_state"]["state_hash"]
    assert snapshot["status_provenance"] == snapshot["canonical_broker_runtime_state"]["status_provenance"]


def test_phase166c_legacy_payload_adapter_cannot_report_connected_when_authentication_fails() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "broker_authenticated": False, "api_reachable": True, "broker_connected": True},
    )
    payload = adapt_canonical_state_to_legacy_broker_payload(state)

    assert payload["transport_status"] == "REACHABLE"
    assert payload["broker_authenticated"] is False
    assert payload["broker_connected"] is False
    assert payload["connected"] is False
    assert payload["execution_allowed"] is False
    assert payload["live_trading_blocked"] is True
    assert payload["broker_execution_armed"] is False


def test_phase166c_success_path_remains_advisory_only() -> None:
    state = build_canonical_broker_runtime_state(broker="COINBASE", mode="live", runtime_payload=_runtime_success())

    assert state.overall_status == OVERALL_GREEN
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False
    assert state.status_provenance["overall"] == "LIVE"
