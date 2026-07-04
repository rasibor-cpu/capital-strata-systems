from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.runtime.broker_startup_selection import (
    broker_summary_from_artifacts,
    build_startup_broker_selection,
    persist_broker_selection,
)
from backend.runtime.coinbase_readiness import (
    coinbase_credential_diagnostics,
    coinbase_live_limit_reconciliation,
    confirm_coinbase_live_read_only,
    evaluate_coinbase_live_read_only,
    merge_readiness_into_broker_state,
    selection_with_coinbase_readiness,
)
from backend.runtime.live_micro_pilot_governor import live_micro_pilot_status
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


def _coinbase_live_selection():
    return build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )


def test_phase153d_missing_coinbase_credentials_fail_safely() -> None:
    status = evaluate_coinbase_live_read_only(_coinbase_live_selection(), env={})

    assert status["broker_connected"] is False
    assert status["broker_authenticated"] is False
    assert status["broker_execution_status"] == "DISABLED"
    assert status["can_live_execute"] is False
    assert status["live_order_permission"] is False
    assert status["auth_reason"] == "missing credentials"
    assert status["credential_diagnostics"]["credential_status"] == "MISSING"
    assert "COINBASE_CDP_KEY_NAME|COINBASE_KEY_NAME|COINBASE_API_KEY" in status["credential_diagnostics"]["missing_credentials"]


def test_phase153d_coinbase_credentials_are_redacted() -> None:
    env = {
        "COINBASE_CDP_KEY_NAME": "organizations/secret-key-name",
        "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----secret-----END PRIVATE KEY-----",
    }
    diagnostics = coinbase_credential_diagnostics(env).as_dict()
    payload = json.dumps(diagnostics)

    assert diagnostics["coinbase_key_present"] is True
    assert diagnostics["coinbase_private_key_present"] is True
    assert diagnostics["redacted"] is True
    assert "secret-key-name" not in payload
    assert "PRIVATE KEY" not in payload


def test_phase153d_live_confirmation_requires_exact_live() -> None:
    accepted = confirm_coinbase_live_read_only("LIVE")
    rejected = confirm_coinbase_live_read_only("live")

    assert accepted["accepted"] is True
    assert accepted["broker_mode"] == "live"
    assert rejected["accepted"] is False
    assert rejected["broker_mode"] == "paper"
    assert rejected["reason"] == "coinbase_live_confirmation_missing_or_invalid"


def test_phase153d_read_only_validation_never_calls_order_submission() -> None:
    class FakeCoinbaseAdapter:
        order_called = False

        def get_account_balance(self):
            return {"balance": "10.00"}

        def get_positions(self):
            return []

        def list_products(self):
            return [{"product_id": "BTC-USD"}]

        def place_market_buy(self, *args, **kwargs):
            self.order_called = True
            raise AssertionError("read-only validation must not submit orders")

        def place_order(self, *args, **kwargs):
            self.order_called = True
            raise AssertionError("read-only validation must not submit orders")

    adapter = FakeCoinbaseAdapter()
    status = evaluate_coinbase_live_read_only(
        _coinbase_live_selection(),
        env={
            "COINBASE_CDP_KEY_NAME": "present",
            "COINBASE_CDP_PRIVATE_KEY": "present",
        },
        adapter_factory=lambda: adapter,
    )

    assert status["broker_connected"] is True
    assert status["broker_authenticated"] is True
    assert status["auth_reason"] == "coinbase_read_only_authentication_verified"
    assert status["read_checks"]["balances"] == "OK"
    assert status["can_live_execute"] is False
    assert adapter.order_called is False


def test_phase153d_phase152a_cad20_governor_is_canonical() -> None:
    reconciliation = coinbase_live_limit_reconciliation(legacy_limit_usd=1.0)
    pilot = live_micro_pilot_status()

    assert reconciliation["canonical_authority"] == "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR"
    assert reconciliation["canonical_live_pilot_limit_cad"] == "20.00"
    assert reconciliation["legacy_secondary_limit_label"] == "LEGACY_SECONDARY_LIMIT"
    assert pilot["canonical_live_capital_authority"] == "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR"
    assert pilot["canonical_live_pilot_limit_cad"] == "20.00"
    assert pilot["broker_submission_guard"] == "REJECT_BEFORE_BROKER"


def test_phase153d_readiness_persists_to_artifacts_and_dashboard(tmp_path: Path, monkeypatch) -> None:
    artifacts = tmp_path / "artifacts"
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setattr(launcher.LauncherConfig, "ACCOUNT_STATE_FILE", str(account))
    monkeypatch.setattr(launcher.LauncherConfig, "SESSION_STATE_FILE", str(session))

    selection = _coinbase_live_selection()
    readiness = evaluate_coinbase_live_read_only(selection, env={})
    selection = selection_with_coinbase_readiness(selection, readiness)
    broker_state = merge_readiness_into_broker_state(selection, readiness)
    persist_broker_selection(
        account_state_path=account,
        session_state_path=session,
        selection=selection,
        broker_state_override=broker_state,
    )

    summary = broker_summary_from_artifacts(
        json.loads(account.read_text(encoding="utf-8")),
        json.loads(session.read_text(encoding="utf-8")),
    )
    frontend = build_frontend_payload({"broker_summary": summary})
    launcher_state = launcher.build_launcher_frontend_state()

    assert summary["credential_diagnostics"]["credential_status"] == "MISSING"
    assert frontend["sections"]["broker"]["coinbase_key_present"] is False
    assert frontend["sections"]["broker"]["auth_reason"] == "missing credentials"
    assert frontend["sections"]["broker"]["canonical_live_pilot_limit_cad"] == "20.00"
    assert frontend["sections"]["broker"]["legacy_secondary_limit_label"] == "LEGACY_SECONDARY_LIMIT"
    assert launcher_state["sections"]["broker"]["execution_scope"] == "LIVE READ-ONLY VALIDATION"
    assert launcher_state["sections"]["broker"]["can_live_execute"] is False


def test_phase153d_legacy_one_dollar_limit_is_secondary_dashboard_state() -> None:
    reconciliation = coinbase_live_limit_reconciliation(legacy_limit_usd=1.0)
    payload = build_frontend_payload(
        {
            "broker_summary": {
                "selected_broker": "COINBASE",
                "broker_mode": "live",
                "broker_execution_status": "DISABLED",
                "limit_reconciliation": reconciliation,
            }
        }
    )
    broker = payload["sections"]["broker"]

    assert broker["canonical_live_capital_authority"] == "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR"
    assert broker["canonical_live_pilot_limit_cad"] == "20.00"
    assert broker["legacy_secondary_limit_label"] == "LEGACY_SECONDARY_LIMIT"
    assert broker["legacy_coinbase_max_live_order_usd"] == 1.0
    assert broker["live_order_permission"] is False


def test_phase153d_mobile_dashboard_renders_readiness_and_canonical_limit(tmp_path: Path, monkeypatch) -> None:
    artifacts = tmp_path / "artifacts"
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setattr(launcher.LauncherConfig, "ACCOUNT_STATE_FILE", str(account))
    monkeypatch.setattr(launcher.LauncherConfig, "SESSION_STATE_FILE", str(session))

    selection = _coinbase_live_selection()
    readiness = evaluate_coinbase_live_read_only(selection, env={})
    selection = selection_with_coinbase_readiness(selection, readiness)
    persist_broker_selection(
        account_state_path=account,
        session_state_path=session,
        selection=selection,
        broker_state_override=merge_readiness_into_broker_state(selection, readiness),
    )

    response = TestClient(launcher.app).get("/mobile")

    assert response.status_code == 200
    assert "Coinbase Key" in response.text
    assert "Auth Reason" in response.text
    assert "Limit Authority" in response.text
    assert "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR" in response.text
    assert "LEGACY_SECONDARY_LIMIT" in response.text
