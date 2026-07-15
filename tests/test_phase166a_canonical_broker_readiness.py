from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
from backend.runtime.canonical_broker_runtime_state import (
    OVERALL_CONTRADICTORY,
    OVERALL_FAIL_CLOSED,
    OVERALL_GREEN,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_UNAVAILABLE,
    CanonicalBrokerRuntimeState,
)
from backend.runtime.canonical_broker_state_adapter import (
    adapt_canonical_state_to_legacy_broker_payload,
)
from backend.runtime.canonical_broker_state_builder import (
    SOURCE_PRECEDENCE,
    build_canonical_broker_runtime_state,
    canonical_state_from_payload,
)
from backend.runtime.canonical_broker_state_registry import (
    CLASS_DEPRECATED,
    CLASS_TEST_ONLY,
    classify_coinbase_environment,
)
from backend.runtime.canonical_broker_state_validator import validate_canonical_broker_state
from backend.runtime.coinbase_readiness import evaluate_coinbase_live_read_only
from backend.runtime.runtime_certification_snapshot import build_runtime_certification_snapshot
from backend.runtime.startup_summary import build_live_startup_summary
from backend.runtime.broker_startup_selection import build_startup_broker_selection
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
        "buying_power": 100.0,
        "margin_status": "PASS",
        "market_data_status": "OK",
        "products_loaded": 10,
        "execution_scope": "LIVE READ-ONLY VALIDATION",
        "order_submission_status": "DISABLED",
        "live_micro_pilot_state": "DISARMED",
        "readiness_state": "FULLY_OPERATIONAL",
        "readiness_score": 97.0,
    }


def test_phase166a_canonical_state_construction_is_immutable_stable_and_safe() -> None:
    state = build_canonical_broker_runtime_state(
        broker="coinbase",
        mode="live",
        runtime_payload=_runtime_success(),
        env={"COINBASE_CDP_KEY_NAME": "present"},
        source_modules=("test", "test"),
        timestamp="2026-07-14T00:00:00+00:00",
    )

    assert state.broker == "COINBASE"
    assert state.credential_status == STATUS_PASS
    assert state.authentication_status == STATUS_PASS
    assert state.overall_status == OVERALL_GREEN
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False
    assert state.source_modules == ("test",)
    replay_payload = state.to_dict()
    replay_payload.pop("state_hash", None)
    assert state.stable_hash() == CanonicalBrokerRuntimeState(**replay_payload).stable_hash()
    with pytest.raises(FrozenInstanceError):
        state.broker = "OANDA"  # type: ignore[misc]


def test_phase166a_stable_serialization_and_replay_are_deterministic() -> None:
    payload = _runtime_success()
    first = build_canonical_broker_runtime_state(runtime_payload=payload, broker="COINBASE", mode="live", timestamp="fixed")
    second = build_canonical_broker_runtime_state(runtime_payload=dict(payload), broker="COINBASE", mode="live", timestamp="fixed")

    assert first.stable_json() == second.stable_json()
    assert first.stable_hash() == second.stable_hash()


def test_phase166a_current_failure_overrides_stale_success() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "broker_authenticated": True},
        auth_trace={
            "authentication": "FAIL",
            "http_status": 401,
            "coinbase_error_code": "COINBASE_HTTP_401",
            "endpoint_verification": {"accounts": {"status": "FAIL"}},
        },
        certification={"certification": "GREEN"},
    )

    assert state.authentication_status == STATUS_FAIL
    assert state.http_status == 401
    assert state.error_code == "COINBASE_HTTP_401"
    assert state.overall_status in {OVERALL_FAIL_CLOSED, OVERALL_CONTRADICTORY}
    assert state.execution_allowed is False


@pytest.mark.parametrize(
    ("error_code", "http_status"),
    [
        ("COINBASE_HTTP_401", 401),
        ("COINBASE_HTTP_403", 403),
        ("COINBASE_TIMEOUT", None),
        ("COINBASE_CLOCK_SKEW", None),
        ("COINBASE_INVALID_JWT", None),
        ("COINBASE_PERMISSION_DENIED", None),
        ("COINBASE_ACCOUNT_UNAVAILABLE", None),
        ("COINBASE_MARKET_DATA_ONLY", None),
        ("COINBASE_BROKER_UNAVAILABLE", None),
    ],
)
def test_phase166a_authentication_evidence_preserves_distinct_failure_codes(error_code: str, http_status: int | None) -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={"selected_broker": "COINBASE", "broker_mode": "live", "credential_status": "PRESENT"},
        auth_trace={"authentication": "FAIL", "coinbase_error_code": error_code, "http_status": http_status},
    )

    assert state.authentication_status == STATUS_FAIL
    assert state.error_code == error_code
    assert state.http_status == http_status


def test_phase166a_environment_classification_and_live_contamination_fail_closed() -> None:
    evidence = classify_coinbase_environment(
        {
            "COINBASE_TEST_ORDER_USD": "1.00",
            "COINBASE_MAX_LIVE_ORDER_USD": "1.00",
            "COINBASE_CDP_KEY_NAME": "present",
        },
        mode="live",
    )
    by_name = {item["variable_name"]: item for item in evidence["findings"]}
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
        env={"COINBASE_TEST_ORDER_USD": "1.00"},
    )

    assert by_name["COINBASE_TEST_ORDER_USD"]["classification"] == CLASS_TEST_ONLY
    assert by_name["COINBASE_TEST_ORDER_USD"]["severity"] == "ERROR"
    assert by_name["COINBASE_MAX_LIVE_ORDER_USD"]["classification"] == CLASS_DEPRECATED
    assert by_name["COINBASE_MAX_LIVE_ORDER_USD"]["severity"] == "WARNING"
    assert state.overall_status == OVERALL_CONTRADICTORY
    assert "live_mode_environment_contamination" in state.contradiction_reasons


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"credential_status": "MISSING", "broker_authenticated": True}, "credentials_missing_but_authentication_pass"),
        ({"authentication": "FAIL", "account_status": "READY"}, "authentication_failed_but_account_ready"),
        ({"balance_status": "UNAVAILABLE", "margin_status": "GREEN"}, "balance_unavailable_but_positive_live_margin"),
        ({"execution_allowed": True, "live_trading_blocked": True}, "execution_allowed_while_live_trading_blocked"),
        ({"broker_execution_armed": True, "live_micro_pilot_state": "DISARMED"}, "broker_execution_armed_while_pilot_disarmed"),
        ({"order_submission_status": "ENABLED", "execution_scope": "READ_ONLY"}, "order_submission_enabled_in_read_only_scope"),
    ],
)
def test_phase166a_contradictions_fail_closed(payload: dict, reason: str) -> None:
    runtime = {**_runtime_success(), **payload}
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=runtime,
        env={"COINBASE_CDP_KEY_NAME": "present"},
        margin_snapshot={"buying_power": 10.0} if "margin_status" in payload else {},
    )

    assert state.overall_status == OVERALL_CONTRADICTORY
    assert reason in state.contradiction_reasons
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False


def test_phase166a_positive_simulated_live_margin_is_rejected() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "balance_status": "UNAVAILABLE"},
        margin_snapshot={"margin_source": "SIMULATED", "buying_power": 10000.0},
    )

    assert state.overall_status == OVERALL_CONTRADICTORY
    assert "positive_simulated_live_margin" in state.contradiction_reasons


def test_phase166a_live_margin_unavailable_aligns_with_balance_unavailable() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={**_runtime_success(), "balances_loaded": False, "buying_power": None},
        margin_snapshot={"margin_source": "LIVE_UNAVAILABLE", "buying_power": 0.0, "margin_available": 0.0},
    )

    assert state.balance_status == STATUS_UNAVAILABLE
    assert state.buying_power_status == STATUS_UNAVAILABLE
    assert state.margin_status == STATUS_UNAVAILABLE
    assert "positive_simulated_live_margin" not in state.contradiction_reasons


def test_phase166a_legacy_one_dollar_is_display_only_and_canonical_limit_precedes() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={
            **_runtime_success(),
            "limit_reconciliation": {
                "legacy_secondary_limit_label": "LEGACY_SECONDARY_LIMIT",
                "legacy_coinbase_max_live_order_usd": "1.00",
            },
        },
    )

    assert str(DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_total_cad) == "20.00"
    assert "20.00" in state.capital_governor
    assert state.order_submission_status != STATUS_PASS


def test_phase166a_adapter_preserves_legacy_payload_from_canonical_state() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=_runtime_success(),
    )
    payload = adapt_canonical_state_to_legacy_broker_payload(state, base_payload={"extra": "kept"})

    assert payload["extra"] == "kept"
    assert payload["canonical_broker_runtime_state"]["broker"] == "COINBASE"
    assert payload["broker_authenticated"] is True
    assert payload["execution_allowed"] is False
    assert payload["live_trading_blocked"] is True
    assert payload["broker_execution_armed"] is False


def test_phase166a_coinbase_readiness_emits_canonical_state_and_hash() -> None:
    class FakeClient:
        def get_accounts(self):
            return {"accounts": [{"currency": "USD", "available_balance": {"value": "10.00"}}]}

        def get_products(self):
            return {"products": [{"product_id": "BTC-USD"}]}

        def get_time(self):
            return {"iso": "2026-07-14T00:00:00Z"}

        def get_product(self, product_id: str):
            return {"product_id": product_id, "price": "1.00"}

    status = evaluate_coinbase_live_read_only(
        build_startup_broker_selection(selected_broker="COINBASE", broker_mode="live", broker_execution_armed=False),
        env={"COINBASE_CDP_KEY_NAME": "present", "COINBASE_CDP_PRIVATE_KEY": "present"},
        adapter_factory=lambda: FakeClient(),
    )

    canonical = status["canonical_broker_runtime_state"]
    assert canonical["broker"] == "COINBASE"
    assert canonical["execution_allowed"] is False
    assert status["state_hash"] == canonical["state_hash"]


def test_phase166a_startup_summary_frontend_and_api_consistency() -> None:
    runtime = _runtime_success()
    startup = build_live_startup_summary(runtime)
    frontend = build_frontend_payload({"broker_summary": {**runtime, "canonical_broker_runtime_state": startup["startup_diagnostics"]["canonical_broker_runtime_state"]}})
    broker = frontend["sections"]["broker"]

    assert startup["startup_diagnostics"]["canonical_broker_runtime_state"]["broker"] == "COINBASE"
    assert broker["canonical_broker_runtime_state"]["broker"] == "COINBASE"
    assert broker["overall_status"] == startup["startup_diagnostics"]["overall_status"]
    assert broker["execution_allowed"] is False


def test_phase166a_runtime_certification_snapshot_contains_canonical_state() -> None:
    snapshot = build_runtime_certification_snapshot(
        "coinbase",
        mode="live",
        cycle_id="phase166a",
        phase156b={
            "broker": "COINBASE",
            "phase156a": "GREEN",
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

    canonical = snapshot["canonical_broker_runtime_state"]
    assert canonical["broker"] == "COINBASE"
    assert canonical["execution_allowed"] is False
    assert snapshot["state_hash"] == canonical["state_hash"]


def test_phase166a_validator_fails_closed_for_invalid_or_malformed_state() -> None:
    state = CanonicalBrokerRuntimeState(
        broker="BAD",
        mode="live",
        credential_status="MISSING",
        authentication_status="PASS",
        readiness_score=float("nan"),
    )
    validation = validate_canonical_broker_state(state)

    assert validation["valid"] is False
    assert validation["contradictory"] is True
    assert validation["execution_allowed"] is False


def test_phase166a_source_precedence_is_explicit() -> None:
    assert SOURCE_PRECEDENCE[0] == "current_live_broker_response"
    assert SOURCE_PRECEDENCE[-1] == "historical_diagnostics_only"


def test_phase166a_missing_canonical_state_fails_closed_when_adapted_from_empty_payload() -> None:
    state = canonical_state_from_payload({})

    assert state.broker == "NONE"
    assert state.overall_status in {OVERALL_FAIL_CLOSED, OVERALL_CONTRADICTORY, "RED", "UNAVAILABLE"}
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False
