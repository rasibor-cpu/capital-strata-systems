from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.runtime.broker_credential_diagnostics import (
    CANONICAL_FAILURE_REASONS,
    authority_reason_from_diagnostics,
    classify_auth_failure,
    diagnose_broker_credentials,
)
from backend.runtime.broker_startup_selection import build_startup_broker_selection
from backend.runtime.coinbase_readiness import evaluate_coinbase_live_read_only
from backend.runtime.live_execution_authority import evaluate_live_execution_authority
from backend.runtime.oanda_readiness import evaluate_oanda_live_read_only
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


FIXED_NOW = datetime(2026, 7, 6, 12, tzinfo=timezone.utc)


def test_phase155d_missing_coinbase_credentials_are_canonical_and_fail_closed() -> None:
    diagnostic = diagnose_broker_credentials("coinbase", env={}, now=FIXED_NOW).as_dict()

    assert diagnostic["broker"] == "coinbase"
    assert diagnostic["credentials_present"] is False
    assert diagnostic["key_present"] is False
    assert diagnostic["failure_reason"] == "KEY_MISSING"
    assert diagnostic["recommended_action"] == "Configure the Coinbase CDP key name"
    assert diagnostic["severity"] == "ERROR"
    assert diagnostic["execution_allowed"] is False
    assert diagnostic["readiness_status"] == "BLOCKED"
    assert diagnostic["live_trading_blocked"] is True
    assert diagnostic["canonical_failure_reason"] == "KEY_MISSING"
    assert diagnostic["missing_credential_fields"]
    assert set(CANONICAL_FAILURE_REASONS) >= {diagnostic["failure_reason"]}


def test_phase155d_malformed_coinbase_pem_and_jwt_failure_are_specific() -> None:
    malformed = diagnose_broker_credentials(
        "coinbase",
        env={
            "COINBASE_CDP_KEY_NAME": "present",
            "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----broken",
        },
        now=FIXED_NOW,
    ).as_dict()
    jwt_failure = diagnose_broker_credentials(
        "coinbase",
        env={
            "COINBASE_CDP_KEY_NAME": "present",
            "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----hidden-----END PRIVATE KEY-----",
        },
        authentication_attempted=True,
        authenticated=False,
        failure_reason="JWT_SIGNATURE_INVALID",
        now=FIXED_NOW,
    ).as_dict()

    assert malformed["pem_valid"] is False
    assert malformed["failure_reason"] == "PEM_INVALID"
    assert "PRIVATE KEY" not in str(malformed)
    assert jwt_failure["failure_reason"] == "JWT_SIGNATURE_INVALID"
    assert authority_reason_from_diagnostics(jwt_failure) == "JWT Signature Invalid"


def test_phase155d_oanda_token_and_account_diagnostics_are_specific() -> None:
    missing_account = diagnose_broker_credentials(
        "oanda",
        env={"OANDA_API_KEY": "present", "OANDA_BASE_URL": "https://api-fxtrade.oanda.com"},
        now=FIXED_NOW,
    ).as_dict()
    invalid_token = diagnose_broker_credentials(
        "oanda",
        env={"OANDA_API_KEY": "present", "OANDA_ACCOUNT_ID": "A1", "OANDA_BASE_URL": "https://api-fxtrade.oanda.com"},
        authentication_attempted=True,
        authenticated=False,
        failure_reason="TOKEN_INVALID",
        now=FIXED_NOW,
    ).as_dict()

    assert missing_account["account_present"] is False
    assert missing_account["failure_reason"] == "ACCOUNT_ID_MISSING"
    assert missing_account["recommended_action"] == "Configure OANDA Account ID"
    assert missing_account["readiness_status"] == "BLOCKED"
    assert invalid_token["token_present"] is True
    assert invalid_token["failure_reason"] == "TOKEN_INVALID"


def test_phase155d_auth_failure_classifier_covers_network_dns_tls_timeout_rate_limit() -> None:
    assert classify_auth_failure(TimeoutError("request timeout")) == "TIMEOUT"
    assert classify_auth_failure(RuntimeError("DNS name resolution failed")) == "DNS_ERROR"
    assert classify_auth_failure(RuntimeError("TLS certificate rejected")) == "TLS_ERROR"
    assert classify_auth_failure(RuntimeError("network connection reset")) == "NETWORK_ERROR"
    assert classify_auth_failure(RuntimeError("rate limit exceeded")) == "RATE_LIMIT"
    assert classify_auth_failure(RuntimeError("broker unavailable")) == "BROKER_UNAVAILABLE"
    assert classify_auth_failure(RuntimeError("unauthorized")) == "UNAUTHORIZED"
    assert classify_auth_failure(RuntimeError("forbidden")) == "FORBIDDEN"


def test_phase155d_readiness_and_authority_consume_specific_diagnostics() -> None:
    selection = build_startup_broker_selection(
        selected_broker="OANDA",
        broker_mode="live",
        broker_execution_armed=False,
        operator_requested_live=True,
    )
    readiness = evaluate_oanda_live_read_only(
        selection,
        env={"OANDA_API_KEY": "present", "OANDA_BASE_URL": "https://api-fxtrade.oanda.com"},
    )
    authority = evaluate_live_execution_authority(readiness).as_dict()

    assert readiness["broker_credential_diagnostics"]["failure_reason"] == "ACCOUNT_ID_MISSING"
    assert readiness["authority_reason"] == "Account ID Missing"
    assert authority["execution_authority"] is False
    assert authority["can_live_execute"] is False
    assert authority["authority_reason"] == "Account ID Missing"


def test_phase155d_coinbase_and_oanda_publish_parity_schema() -> None:
    coinbase = diagnose_broker_credentials("coinbase", env={}, now=FIXED_NOW).as_dict()
    oanda = diagnose_broker_credentials("oanda", env={}, now=FIXED_NOW).as_dict()

    assert set(coinbase) == set(oanda)
    assert coinbase["execution_allowed"] is False
    assert oanda["execution_allowed"] is False
    assert coinbase["broker_name"] == "COINBASE"
    assert oanda["broker_name"] == "OANDA"


def test_phase156a_valid_credentials_are_reported_as_ready_without_leaking_secrets() -> None:
    coinbase = diagnose_broker_credentials(
        "coinbase",
        env={
            "COINBASE_CDP_KEY_NAME": "present",
            "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\nhidden\n-----END PRIVATE KEY-----",
        },
        now=FIXED_NOW,
    ).as_dict()
    oanda = diagnose_broker_credentials(
        "oanda",
        env={
            "OANDA_API_KEY": "present",
            "OANDA_ACCOUNT_ID": "A1",
            "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
        },
        now=FIXED_NOW,
    ).as_dict()

    assert coinbase["credentials_present"] is True
    assert coinbase["readiness_status"] == "READY"
    assert coinbase["live_trading_blocked"] is True
    assert oanda["credentials_present"] is True
    assert oanda["readiness_status"] == "READY"
    assert oanda["failure_reason"] == "NONE"
    assert "hidden" not in str(coinbase)
    assert "A1" not in str(oanda)
    assert "api-fxtrade.oanda.com" not in str(oanda)


def test_phase156a_unknown_broker_is_safe_and_fail_closed() -> None:
    diagnostic = diagnose_broker_credentials("mystery-broker", env={"SECRET": "hidden"}, now=FIXED_NOW).as_dict()

    assert diagnostic["broker"] == "mystery-broker"
    assert diagnostic["broker_name"] == "MYSTERY-BROKER"
    assert diagnostic["failure_reason"] == "MISSING_CREDENTIALS"
    assert diagnostic["readiness_status"] == "FAILED"
    assert diagnostic["live_trading_blocked"] is True
    assert diagnostic["execution_allowed"] is False
    assert "hidden" not in str(diagnostic)


def test_phase155d_frontend_and_api_expose_read_only_diagnostics() -> None:
    diagnostic = diagnose_broker_credentials(
        "oanda",
        env={"OANDA_API_KEY": "present", "OANDA_BASE_URL": "https://api-fxtrade.oanda.com"},
        now=FIXED_NOW,
    ).as_dict()
    state = DashboardHydrationCoordinator().hydrate(
        broker_payload={
            "selected_broker": "OANDA",
            "broker_credential_diagnostics": diagnostic,
            "credential_diagnostics": {"broker_credential_diagnostics": diagnostic},
        }
    )
    frontend = build_frontend_payload(state)
    section = frontend["sections"]["broker_credential_diagnostics"]

    assert section["broker"] == "OANDA"
    assert section["failure_reason"] == "ACCOUNT_ID_MISSING"
    assert section["recommended_action"] == "Configure OANDA Account ID"
    assert section["execution_allowed"] is False

    response = TestClient(create_app(lambda: state)).get("/api/v1/broker-credential-diagnostics")
    assert response.status_code == 200
    assert response.json()["section"] == "broker_credential_diagnostics"
    assert response.json()["data"]["failure_reason"] == "ACCOUNT_ID_MISSING"


def test_phase156a_diagnostics_include_canonical_readiness_aliases_in_payloads() -> None:
    diagnostic = diagnose_broker_credentials(
        "oanda",
        env={"OANDA_API_KEY": "present", "OANDA_BASE_URL": "https://api-fxtrade.oanda.com"},
        now=FIXED_NOW,
    ).as_dict()

    assert diagnostic["broker_name"] == "OANDA"
    assert diagnostic["canonical_failure_reason"] == "ACCOUNT_ID_MISSING"
    assert diagnostic["remediation_hint"] == "Configure OANDA Account ID"
    assert diagnostic["missing_credential_fields"] == diagnostic["missing_credentials"]


def test_phase155d_mobile_dashboard_and_api_render_diagnostics(monkeypatch) -> None:
    diagnostic = diagnose_broker_credentials("oanda", env={}, now=FIXED_NOW).as_dict()
    monkeypatch.setattr(
        launcher,
        "get_broker_startup_summary",
        lambda: {
            "selected_broker": "OANDA",
            "broker_credential_diagnostics": diagnostic,
            "credential_diagnostics": {"broker_credential_diagnostics": diagnostic},
        },
    )

    response = TestClient(launcher.app).get("/api/v1/broker-credential-diagnostics")
    assert response.status_code == 200
    assert response.json()["data"]["broker"] == "OANDA"
    assert response.json()["data"]["execution_allowed"] is False

    page = TestClient(launcher.app).get("/mobile")
    assert page.status_code == 200
    assert "Broker Credential Diagnostics" in page.text
    assert "Recommended Action" in page.text


def test_phase155d_coinbase_readiness_remains_fail_closed_with_specific_reason() -> None:
    selection = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
        operator_requested_live=True,
    )
    readiness = evaluate_coinbase_live_read_only(selection, env={})

    assert readiness["broker_credential_diagnostics"]["failure_reason"] == "KEY_MISSING"
    assert readiness["authority_reason"] == "Credentials Invalid"
    assert readiness["execution_authority"] is False
    assert readiness["can_live_execute"] is False
