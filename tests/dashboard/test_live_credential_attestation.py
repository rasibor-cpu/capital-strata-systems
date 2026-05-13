from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_live_credential_attestation_payload,
)
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.live_credential_attestation import (
    LIVE_CREDENTIALS_ATTESTED,
    LIVE_CREDENTIALS_INCOMPLETE,
    LIVE_CREDENTIALS_NOT_CONFIGURED,
    LIVE_CREDENTIAL_ATTESTATION_PAYLOAD_VERSION,
    attest_live_credentials,
)
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads


def test_coinbase_credential_attestation_uses_names_only_and_existing_path(tmp_path) -> None:
    private_key = tmp_path / "coinbase.pem"
    private_key.write_text("PRIVATE-KEY-SHOULD-NOT-LEAK", encoding="utf-8")
    env = {
        "COINBASE_CDP_KEY_NAME": "organizations/example/apiKeys/example",
        "COINBASE_CDP_PRIVATE_KEY_PATH": str(private_key),
    }

    payload = attest_live_credentials(brokers=["coinbase"], env=env).as_dict()
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["payload_version"] == LIVE_CREDENTIAL_ATTESTATION_PAYLOAD_VERSION
    assert payload["status"] == LIVE_CREDENTIALS_ATTESTED
    assert payload["ready_broker_count"] == 1
    assert "organizations/example" not in encoded
    assert str(private_key) not in encoded
    assert "PRIVATE-KEY-SHOULD-NOT-LEAK" not in encoded
    assert "COINBASE_CDP_KEY_NAME" in encoded
    assert "COINBASE_CDP_PRIVATE_KEY_PATH" in encoded


def test_oanda_credential_attestation_detects_missing_account_id() -> None:
    payload = attest_live_credentials(
        brokers=["oanda"],
        env={"OANDA_API_TOKEN": "TOKEN-SHOULD-NOT-LEAK"},
    ).as_dict()
    broker = payload["broker_attestations"][0]
    missing_codes = {
        requirement["code"]
        for requirement in broker["requirements"]
        if not requirement["present"]
    }
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["status"] == LIVE_CREDENTIALS_INCOMPLETE
    assert broker["status"] == LIVE_CREDENTIALS_INCOMPLETE
    assert "oanda_account_id" in missing_codes
    assert "TOKEN-SHOULD-NOT-LEAK" not in encoded


def test_unknown_broker_attestation_fails_closed() -> None:
    payload = attest_live_credentials(brokers=["unknown"], env={}).as_dict()

    assert payload["status"] == LIVE_CREDENTIALS_NOT_CONFIGURED
    assert payload["broker_count"] == 0
    assert payload["ready_broker_count"] == 0


def test_live_credential_attestation_api_exposes_redacted_payload() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    app = create_app(lambda: state)
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_live_credential_attestation_payload()
    encoded = json.dumps(payload, sort_keys=True)

    assert "/api/v1/live-credential-attestation" in routes
    assert payload["payload_version"] == LIVE_CREDENTIAL_ATTESTATION_PAYLOAD_VERSION
    assert payload["security"]["contains_secret_values"] is False
    assert payload["security"]["network_calls_performed"] is False
    assert "api_secret" not in encoded.lower()
