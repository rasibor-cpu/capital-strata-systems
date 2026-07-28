import os
import pytest
from unittest import mock
from backend.app.brokers.live_readiness_certifier import certify_live_readiness
from backend.app.brokers.execution_boundary import validate_execution_boundary
from backend.app.brokers.oanda_adapter import OandaAdapter
from backend.app.brokers.credential_loader import CredentialLoadError, _load_env_fallback_credentials


class _EmptyCredentialProfile:
    validation_status = "FAIL"
    key_identifier_present = False
    private_key_present = False
    loaded_files = ()

    def credentials_for_broker(self):
        return {}

    def redacted_diagnostics(self):
        return {
            "validation_status": self.validation_status,
            "loaded_files": [],
            "credentials_present": False,
        }

def test_paper_mode_cannot_use_live_capital_source():
    # Prove paper mode rejects LIVE capital source labels completely
    result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="paper",
        asset_class="fx",
        capital_source_label="LIVE",
        balance_source="LIVE",
        dry_run_order={"broker": "oanda", "asset_class": "fx", "dry_run": True, "quantity": 100, "symbol": "EUR_USD", "side": "BUY"},
        session={"user_id": "test", "role": "ADMIN"},
        portfolio_state={"nav": 1000},
        engine_mode="SAFE",
        operator_approval={"approved": True, "approver_role": "ADMIN", "approval_id": "123"}
    )
    
    assert "FAIL" in result.status
    assert "paper_mode_cannot_use_live_capital" in result.blocking_reasons


def test_live_mode_cannot_use_paper_capital_source():
    # Prove live mode rejects FAKE capital source labels
    result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="live",
        asset_class="fx",
        capital_source_label="SIMULATED",
        balance_source="BROKER",
        dry_run_order={"broker": "oanda", "asset_class": "fx", "dry_run": True, "quantity": 100, "symbol": "EUR_USD", "side": "BUY"},
        session={"user_id": "test", "role": "ADMIN"},
        portfolio_state={"nav": 1000},
        engine_mode="SAFE",
        operator_approval={"approved": True, "approver_role": "ADMIN", "approval_id": "123"}
    )
    
    assert "FAIL" in result.status
    assert "live_mode_requires_real_capital_source" in result.blocking_reasons


def test_live_mode_cannot_silently_fallback_to_simulated_capital():
    boundary = validate_execution_boundary(selected_mode="live", capital_source_label="SIMULATED")
    assert boundary.allowed is False
    assert boundary.reason == "live_mode_cannot_use_simulated_capital"


@mock.patch("backend.app.brokers.credential_loader.load_dotenv")
@mock.patch(
    "backend.app.brokers.credential_loader._canonical_profile_credentials",
    return_value=_EmptyCredentialProfile(),
)
@mock.patch.dict(os.environ, clear=True)
def test_missing_credentials_fails_closed(mock_profile, mock_load_dotenv):
    # If no env vars and no files exist, credentials load must fail
    assert _load_env_fallback_credentials("oanda", "paper") is None
    assert _load_env_fallback_credentials("coinbase", "paper") is None

    result = certify_live_readiness(
        selected_broker="oanda",
        broker_mode="paper",
        asset_class="fx",
        capital_source_label="SIMULATED",
        balance_source="SIMULATED",
        dry_run_order={"broker": "oanda", "asset_class": "fx", "dry_run": True, "quantity": 100, "symbol": "EUR_USD", "side": "BUY"},
        session={"user_id": "test", "role": "ADMIN"},
        portfolio_state={"nav": 1000},
        engine_mode="SAFE",
        operator_approval={"approved": True, "approver_role": "ADMIN", "approval_id": "123"},
        credential_base_dir="/tmp/does/not/exist/surely"
    )
    
    assert "FAIL" in result.status
    assert "credentials_missing" in result.blocking_reasons


@mock.patch("backend.app.brokers.credential_loader.load_dotenv")
@mock.patch.dict(os.environ, {"OANDA_ENABLE_LIVE_TRADING": "0", "OANDA_API_KEY": "fake_key", "OANDA_ACCOUNT_ID": "fake_id", "OANDA_BASE_URL": "http://fake"})
def test_oanda_adapter_paper_mode_enforces_live_trading_firewall(mock_load_dotenv):
    # Prove that even with credentials, if live trading flag is off, the firewall blocks.
    # _allow_live_order_execution() was replaced by _evaluate_live_firewall() in the
    # OANDA live firewall hardening patch. The new API provides per-condition audit trails.
    adapter = OandaAdapter()
    assert adapter.is_configured() is True
    assert adapter.allow_live_trades is False  # env var gate still present as attribute

    firewall = adapter._evaluate_live_firewall()
    assert firewall.allowed is False
    assert "condition_1" in firewall.denied_reason  # blocks at OANDA_ENABLE_LIVE_TRADING

    order_result = adapter.place_order(symbol="EUR_USD", units=10, side="BUY")
    assert order_result["ok"] is False
    assert order_result["error"] == "oanda_legacy_writes_quarantined"
    assert order_result["primary_denial_code"] == "oanda_legacy_writes_quarantined"
    assert any("condition_1" in item for item in order_result["secondary_denial_codes"])
    assert order_result["network_attempted"] is False


@mock.patch("backend.app.brokers.credential_loader.load_dotenv")
@mock.patch.dict(os.environ, {"OANDA_ENABLE_LIVE_TRADING": "1", "OANDA_API_KEY": "my_secret_token_123", "OANDA_ACCOUNT_ID": "fake_id"})
def test_no_secrets_are_printed_in_audit_payload(mock_load_dotenv):
    # Prove the certifier REDACTS secrets
    from backend.app.brokers.live_readiness_certifier import _json_safe
    
    safe_data = _json_safe({
        "status": "PASS",
        "api_key": "sensitive_session_token_xyz"
    })
    
    # We must ensure that string conversion of the payload has REDACTED for the token
    payload_str = str(safe_data)
    assert "sensitive_session_token_xyz" not in payload_str
    assert "REDACTED" in payload_str
