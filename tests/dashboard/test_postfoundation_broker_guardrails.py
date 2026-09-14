from __future__ import annotations

import json
from datetime import datetime, timezone

import dashboard.runtime.live_credential_attestation as credential_attestation
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.broker_adapter_conformance import (
    build_broker_adapter_conformance_payload,
    certify_broker_adapter_conformance,
)
from dashboard.runtime.broker_live_dry_run_certification import (
    BrokerDryRunCertificationInput,
    build_broker_live_dry_run_certification,
)


def test_dry_run_certification_fails_closed_without_probe():
    payload = build_broker_live_dry_run_certification(
        BrokerDryRunCertificationInput(
            broker="OANDA",
            broker_mode="live",
            broker_connected=True,
            readiness_status="BROKER_READY",
            reconciliation_status="BROKER_RECONCILED",
            credential_ready=True,
            dry_run_probe=None,
        )
    )
    assert payload["status"] == "FAIL"
    assert "DRY_RUN_PROBE_MISSING" in payload["blocking_reasons"]
    assert payload["execution_allowed"] is False


def test_dry_run_certification_pass_does_not_authorize_execution():
    payload = build_broker_live_dry_run_certification(
        BrokerDryRunCertificationInput(
            broker="OANDA",
            broker_mode="live",
            broker_connected=True,
            readiness_status="BROKER_READY",
            reconciliation_status="BROKER_RECONCILED",
            credential_ready=True,
            dry_run_probe={
                "dry_run": True,
                "submitted_to_broker": False,
                "would_place_live_order": False,
                "symbol": "EUR_USD",
                "quantity": 1,
            },
        )
    )
    assert payload["status"] == "PASS"
    assert payload["execution_allowed"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["live_trading_authorized"] is False


def test_unknown_broker_conformance_fails_closed():
    report = certify_broker_adapter_conformance("does-not-exist").as_dict()
    assert report["status"] == "FAIL_CLOSED"
    assert report["execution_allowed"] is False


def test_conformance_collection_is_json_safe_and_read_only():
    payload = build_broker_adapter_conformance_payload()
    encoded = json.dumps(payload)
    assert encoded
    assert payload["read_only"] is True
    assert payload["execution_allowed"] is False
    assert {row["broker"] for row in payload["reports"]} >= {"coinbase", "oanda", "alpaca"}


def test_credential_attestation_never_returns_secret_values(monkeypatch, tmp_path):
    monkeypatch.setattr(
        credential_attestation,
        "load_credentials",
        lambda *args, **kwargs: {
            "OANDA_API_KEY": "TOP-SECRET-TOKEN",
            "OANDA_ACCOUNT_ID": "123456789",
        },
    )
    payload = credential_attestation.attest_live_credentials(
        "oanda",
        base_dir=tmp_path,
        now_utc=datetime(2026, 9, 14, tzinfo=timezone.utc),
    )
    encoded = json.dumps(payload)
    assert payload["status"] == "READY"
    assert payload["secret_values_included"] is False
    assert payload["local_paths_included"] is False
    assert "TOP-SECRET-TOKEN" not in encoded
    assert "123456789" not in encoded


def test_credential_attestation_fails_closed_when_required_group_missing(monkeypatch):
    monkeypatch.setattr(
        credential_attestation,
        "load_credentials",
        lambda *args, **kwargs: {"OANDA_ACCOUNT_ID": "123"},
    )
    payload = credential_attestation.attest_live_credentials("oanda")
    assert payload["status"] == "NOT_READY"
    assert payload["required_fields_ready"] is False


def test_api_exposes_postfoundation_guardrail_routes():
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/broker-live-dry-run-certification" in routes
    assert "/api/v1/broker-adapter-conformance" in routes
    assert "/api/v1/live-credential-attestation" in routes
