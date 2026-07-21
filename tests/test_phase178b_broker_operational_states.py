"""Phase 178B — canonical broker operational-state tests."""

from __future__ import annotations

import logging

from backend.app.brokers.canonical_tier1 import TIER1_BROKERS, get_canonical_broker_registry
from backend.app.brokers.live_read_only import build_live_read_only_contract
from backend.app.brokers.oanda_adapter import OandaAdapter
from backend.app.brokers.operational_adapter import (
    BinanceOperationalAdapter,
    CoinbaseOperationalAdapter,
    OandaOperationalAdapter,
    QuestradeOperationalAdapter,
    get_operational_adapter,
    tier1_operational_states,
)
from backend.app.brokers.operational_state import (
    ALLOWED_TRANSITIONS,
    BrokerCapability,
    BrokerOperationalState,
    capture_unexpected_fault,
    operation_result,
    state_definitions,
    validate_transition,
)
from backend.app.brokers.operational_observability import log_operation_result, reset_expected_log_deduplication
from backend.broker_reporting import build_broker_executive_report_package
from backend.broker.coinbase_adapter import CoinbaseAdapter
from backend.brokers.questrade.token_lifecycle import TokenLifecycle
from backend.options.options_income_data_resolver import resolve_options_income_advisory_data
from dashboard.enterprise_shell.reports_hub import build_reports_hub_payload
from backend.runtime.broker_readiness_consolidation import build_canonical_broker_readiness
from backend.runtime.runtime_mode import resolve_runtime_mode
from dashboard.mission_control.pages.broker_management import render as render_broker_management
from dashboard.mission_control.routes import create_mission_control_router
from dashboard.runtime.frontend_contract import broker as build_frontend_broker


def test_expected_condition_returns_structured_result() -> None:
    result = operation_result(
        broker="QUESTRADE",
        operation="account",
        state=BrokerOperationalState.CONFIGURATION_REQUIRED,
        failure_code="CONFIGURATION_REQUIRED",
        operator_message="Configuration required",
        recommended_action="Configure read-only settings",
    ).as_dict()
    required = {
        "broker",
        "operation",
        "state",
        "success",
        "retryable",
        "expected_condition",
        "failure_code",
        "operator_message",
        "technical_message",
        "recommended_action",
        "capability",
        "execution_allowed",
        "advisory_allowed",
        "data",
        "provenance",
        "received_at",
        "freshness",
        "correlation_id",
        "state_hash",
    }
    assert required <= result.keys()
    assert result["success"] is False
    assert result["expected_condition"] is True
    assert result["execution_allowed"] is False


def test_state_definitions_and_valid_transitions() -> None:
    definitions = state_definitions()
    assert "TOKEN_REFRESH_REQUIRED" in definitions["states"]
    assert "OPTION_CHAIN_UNAVAILABLE" in definitions["states"]
    assert definitions["execution_states_available"] is False
    assert validate_transition("AUTHENTICATED", "TOKEN_REFRESH_REQUIRED").success is True
    invalid = validate_transition("NOT_INITIALIZED", "READ_ONLY_READY").as_dict()
    assert invalid["success"] is False
    assert invalid["failure_code"] == "INVALID_STATE_TRANSITION"
    assert invalid["expected_condition"] is False
    assert set(ALLOWED_TRANSITIONS) == set(BrokerOperationalState)
    assert validate_transition("OPTION_CHAIN_READY", "ADVISORY_READY").success is True
    assert validate_transition("ADVISORY_READY", "OPTION_CHAIN_UNAVAILABLE").success is True
    assert validate_transition("EXECUTION_BLOCKED", "READ_ONLY_READY").success is True


def test_questrade_no_config_never_raises() -> None:
    adapter = QuestradeOperationalAdapter()
    assert adapter.readiness()["state"] == "CONFIGURATION_REQUIRED"
    assert adapter.account()["state"] == "CONFIGURATION_REQUIRED"
    assert adapter.holdings()["state"] == "CONFIGURATION_REQUIRED"
    assert adapter.market_data("XIU.TO")["state"] == "CONFIGURATION_REQUIRED"
    chain = adapter.option_chain("XIU.TO")
    assert chain["state"] == "OPTION_CHAIN_PROVIDER_REQUIRED"
    assert chain["expected_condition"] is True
    assert chain["execution_allowed"] is False
    holdings_capability = adapter.capability(BrokerCapability.HOLDINGS)
    assert holdings_capability["state"] == "HOLDINGS_UNAVAILABLE"
    assert holdings_capability["data"]["declared_supported"] is True
    assert holdings_capability["data"]["operationally_ready"] is False
    option_chain_capability = adapter.capability(BrokerCapability.OPTION_CHAIN)
    assert option_chain_capability["state"] == "OPTION_CHAIN_PROVIDER_REQUIRED"
    assert option_chain_capability["data"]["declared_supported"] is True
    assert option_chain_capability["success"] is False


def test_coinbase_and_binance_credentials_required() -> None:
    for adapter in (CoinbaseOperationalAdapter(), BinanceOperationalAdapter()):
        result = adapter.authenticate()
        assert result["state"] == "CREDENTIALS_REQUIRED"
        assert result["failure_code"] == "CREDENTIALS_REQUIRED"
        assert result["expected_condition"] is True
        option_chain = adapter.capability(BrokerCapability.OPTION_CHAIN)
        assert option_chain["state"] == "OPTION_CHAIN_UNAVAILABLE"
        assert option_chain["data"]["supported"] is False
        crypto = adapter.capability(BrokerCapability.CRYPTO)
        assert crypto["data"]["declared_supported"] is True
        assert crypto["data"]["operationally_ready"] is False
        assert crypto["state"] == "CREDENTIALS_REQUIRED"
        assert crypto["success"] is False

    live_coinbase = CoinbaseAdapter(paper_mode=False)
    assert live_coinbase.place_market_buy(product_id="BTC-USD", size_usd=1)["state"] == "EXECUTION_BLOCKED"
    assert live_coinbase.place_market_sell(product_id="BTC-USD", size_asset=0.1)["state"] == "EXECUTION_BLOCKED"
    assert live_coinbase.get_candles("BTC-USD", "UNSUPPORTED")["state"] == "MARKET_DATA_UNAVAILABLE"


def test_oanda_configuration_account_and_environment_conditions() -> None:
    assert OandaOperationalAdapter().readiness()["state"] == "CONFIGURATION_REQUIRED"
    configured = {
        "OANDA_BASE_URL": "https://api-fxpractice.oanda.com",
        "OANDA_API_TOKEN": "present-for-test-only",
    }
    account = OandaOperationalAdapter(
        configuration=configured,
        evidence={"authenticated": True, "evidence_verified": True},
    ).account()
    assert account["state"] == "ACCOUNT_REQUIRED"
    mismatch = OandaOperationalAdapter(
        configuration={**configured, "OANDA_ACCOUNT_ID": "sanitized", "OANDA_ENVIRONMENT": "practice"},
        evidence={"authenticated": True, "expected_environment": "live"},
    ).readiness()
    assert mismatch["failure_code"] == "OANDA_ENVIRONMENT_MISMATCH"
    assert mismatch["state"] == "CONFIGURATION_REQUIRED"
    assert OandaOperationalAdapter().capability(BrokerCapability.OPTION_CHAIN)["state"] == "OPTION_CHAIN_UNAVAILABLE"
    fx = OandaOperationalAdapter().capability(BrokerCapability.FX)
    assert fx["data"]["declared_supported"] is True
    assert fx["data"]["operationally_ready"] is False
    assert fx["state"] == "CONFIGURATION_REQUIRED"
    assert fx["success"] is False
    legacy = OandaAdapter(credentials={})
    response = legacy._request_json("GET", "/v3/accounts")
    assert response["error"] == "CONFIGURATION_REQUIRED"
    assert response["operation_result"]["expected_condition"] is True


def test_token_provider_and_rate_limit_states() -> None:
    config = {"COINBASE_API_KEY": "test", "COINBASE_API_SECRET": "test"}
    expired = CoinbaseOperationalAdapter(configuration=config, evidence={"token_expired": True}).account()
    assert expired["state"] == "TOKEN_REFRESH_REQUIRED"
    assert expired["retryable"] is True

    unavailable = CoinbaseOperationalAdapter(
        configuration=config,
        evidence={"provider_unavailable": True},
    ).market_data("BTC-USD")
    assert unavailable["state"] == "PROVIDER_UNAVAILABLE"
    assert unavailable["retryable"] is True

    limited = CoinbaseOperationalAdapter(
        configuration=config,
        evidence={"rate_limited": True},
    ).market_data("BTC-USD")
    assert limited["state"] == "RATE_LIMITED"
    assert limited["retryable"] is True
    lifecycle = TokenLifecycle()
    assert lifecycle.status()["state"] == "CREDENTIALS_REQUIRED"
    assert lifecycle.refresh()["state"] == "TOKEN_REFRESH_REQUIRED"
    assert lifecycle.refresh()["retryable"] is True


def test_read_only_ready_and_capability_independence() -> None:
    config = {"COINBASE_API_KEY": "test", "COINBASE_API_SECRET": "test"}
    adapter = CoinbaseOperationalAdapter(
        configuration=config,
        evidence={"authenticated": True, "market_data_ready": True, "evidence_verified": True},
    )
    assert adapter.readiness()["state"] == "READ_ONLY_READY"
    assert adapter.capability(BrokerCapability.CRYPTO)["success"] is True
    assert adapter.capability(BrokerCapability.OPTION_CHAIN)["state"] == "OPTION_CHAIN_UNAVAILABLE"
    assert adapter.capability(BrokerCapability.EXECUTION)["state"] == "EXECUTION_BLOCKED"


def test_live_read_only_operations_are_canonical_results() -> None:
    contract = build_live_read_only_contract("QUESTRADE").as_dict()
    expected = {
        "authenticate",
        "account",
        "balances",
        "holdings",
        "positions",
        "market_data",
        "products",
        "health",
        "readiness",
    }
    assert expected <= contract["operation_results"].keys()
    assert contract["operation_results"]["readiness"]["expected_condition"] is True
    assert contract["execution_allowed"] is False
    assert contract["order_submission"] == "BLOCKED"


def test_readiness_and_certification_mapping() -> None:
    source = {
        "selected_broker": "COINBASE",
        "configuration": {"COINBASE_API_KEY": "test", "COINBASE_API_SECRET": "test"},
        "authenticated": True,
        "market_data_ready": True,
        "evidence_verified": True,
    }
    readiness = build_canonical_broker_readiness(broker_section=source)
    assert readiness["operational_state"] == "READ_ONLY_READY"
    assert readiness["canonical_certification"] == "READ_ONLY_READY"
    assert readiness["ready_for_execution"] is False


def test_tier1_rows_mission_control_and_mobile_mapping() -> None:
    registry = get_canonical_broker_registry()
    rows = registry.mission_control_rows(selected_broker="NONE")
    assert {row["broker"] for row in rows} == set(TIER1_BROKERS)
    for row in rows:
        assert row["operational_state"] in {
            "CONFIGURATION_REQUIRED",
            "CREDENTIALS_REQUIRED",
        }
        assert row["expected_condition"] is True
        assert row["execution_state"] == "EXECUTION_BLOCKED"
        assert "OPTION_CHAIN" in row["capability_states"]

    frontend = build_frontend_broker({"broker_summary": {"selected_broker": "COINBASE"}})
    assert frontend["canonical_operational_state"] == "CREDENTIALS_REQUIRED"
    assert frontend["account_state"]
    assert frontend["market_data_state"]
    assert frontend["option_chain_state"] == "OPTION_CHAIN_UNAVAILABLE"
    assert frontend["execution_state"] == "EXECUTION_BLOCKED"
    assert frontend["details_link"] == "/mission-control/broker-management"

    html = render_broker_management(
        {
            "brokers": {
                "broker_list": rows,
                "active_broker": {},
                "primary_roles": registry.primary_roles(),
            }
        }
    )
    assert "Required Action" in html
    assert "Expected Condition" in html
    assert "Option Chain" in html
    assert "Traceback" not in html


def test_options_income_consumes_capability_state() -> None:
    coinbase = resolve_options_income_advisory_data(
        broker="COINBASE",
        underlying_symbols=["SPY"],
    )
    assert coinbase["broker_operational_state"]["operational_state"] == "CREDENTIALS_REQUIRED"
    assert coinbase["broker_option_chain_state"]["state"] == "OPTION_CHAIN_UNAVAILABLE"
    assert coinbase["broker_listed_options_compatible"] is False
    assert coinbase["readiness_status"] == "DATA_DEPENDENCY_BLOCKED"

    questrade = resolve_options_income_advisory_data(
        broker="QUESTRADE",
        underlying_symbols=["XIU.TO"],
    )
    assert questrade["broker_option_chain_state"]["state"] == "OPTION_CHAIN_PROVIDER_REQUIRED"
    assert questrade["broker_expected_condition"] is True
    assert questrade["readiness_status"] == "DATA_DEPENDENCY_BLOCKED"


def test_broker_report_contains_operational_states_and_pagination() -> None:
    report = build_broker_executive_report_package(commit_reference="test").as_dict()
    for broker in TIER1_BROKERS:
        assert "expected_condition" in report["broker_readiness"][broker]
        assert "capability_states" in report["per_broker"][broker]
    titles = [page.get("title") for page in report["document"]["pages"]]
    assert any("Operational and Capability States" in str(title) for title in titles)
    assert report["document"]["presentation"]["page_size"] == "A4"
    assert report["execution_allowed"] is False
    hub = build_reports_hub_payload(role="VIEWER", surface="mission_control")
    cards = [card for group in hub["groups"] for card in group.get("reports", [])]
    broker_card = next(card for card in cards if card.get("report_id") == "broker_executive")
    assert broker_card["view_href"] == "/api/reports/broker_executive/view"


def test_api_routes_are_get_only() -> None:
    router = create_mission_control_router(lambda: {})
    paths = {getattr(route, "path", ""): set(getattr(route, "methods", set()) or set()) for route in router.routes}
    assert "/api/brokers/states" in paths
    assert "/api/brokers/{broker}/status" in paths
    assert "/api/brokers/{broker}/capabilities" in paths
    assert "/api/brokers/{broker}/readiness" in paths
    for path, methods in paths.items():
        if path.startswith("/api/brokers"):
            assert methods == {"GET"}


def test_sanitization_and_unexpected_fault_boundary() -> None:
    safe = operation_result(
        broker="COINBASE",
        operation="test",
        state="FAILED",
        expected_condition=False,
        technical_message="Bearer super-secret-token",
        data={"access_token": "secret", "nested": {"account_number": "123456"}},
    ).as_dict()
    rendered = str(safe)
    assert "super-secret-token" not in rendered
    assert "123456" not in rendered

    def boom() -> None:
        raise RuntimeError("provider schema violated")

    failed = capture_unexpected_fault("COINBASE", "market_data", boom)
    assert failed.state is BrokerOperationalState.FAILED
    payload = failed.as_dict()
    assert payload["expected_condition"] is False
    assert payload["correlation_id"]


def test_operational_logging_levels_deduplication_and_sanitization(caplog) -> None:
    reset_expected_log_deduplication()
    caplog.set_level(logging.INFO, logger="css.brokers.operational")
    expected = operation_result(
        broker="QUESTRADE",
        operation="readiness",
        state=BrokerOperationalState.CONFIGURATION_REQUIRED,
        technical_message="Bearer should-never-appear",
    ).as_dict()
    log_operation_result(expected)
    log_operation_result(expected)
    assert caplog.text.count("QUESTRADE readiness state=CONFIGURATION_REQUIRED") == 1
    assert "should-never-appear" not in caplog.text

    degraded = operation_result(
        broker="COINBASE",
        operation="market_data",
        state=BrokerOperationalState.PROVIDER_UNAVAILABLE,
        retryable=True,
    ).as_dict()
    log_operation_result(degraded)
    assert any(record.levelno == logging.WARNING and "PROVIDER_UNAVAILABLE" in record.message for record in caplog.records)

    unexpected = capture_unexpected_fault("OANDA", "account", lambda: (_ for _ in ()).throw(RuntimeError("fault")))
    log_operation_result(unexpected.as_dict())
    assert any(record.levelno == logging.ERROR and "state=FAILED" in record.message for record in caplog.records)


def test_compatibility_aliases_derive_from_canonical_states() -> None:
    assert BrokerOperationalState.REGISTERED is BrokerOperationalState.NOT_INITIALIZED
    assert BrokerOperationalState.UNCONFIGURED is BrokerOperationalState.CONFIGURATION_REQUIRED
    assert BrokerOperationalState.LIVE_READ_ONLY is BrokerOperationalState.READ_ONLY_READY
    contract = build_live_read_only_contract("COINBASE").as_dict()
    assert contract["compatibility"]["canonical_source"] == "operation_results.readiness"


def test_execution_runtime_and_registry_safety_unchanged() -> None:
    runtime = resolve_runtime_mode()
    assert runtime.runtime_mode.value == "DISABLED"
    assert runtime.execution_enabled is False
    states = tier1_operational_states()
    assert states["execution_allowed"] is False
    assert states["execution_state"] == "EXECUTION_BLOCKED"
    assert set(states["brokers"]) == set(TIER1_BROKERS)
    assert "IBKR" not in states["brokers"]
