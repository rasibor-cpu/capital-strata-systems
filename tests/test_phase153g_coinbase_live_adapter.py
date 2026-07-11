from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.accounting.real_balance_engine import RealBalanceEngine
from backend.runtime.broker_startup_selection import (
    broker_summary_from_artifacts,
    build_startup_broker_selection,
    persist_broker_selection,
)
from backend.runtime.coinbase_live_adapter import (
    CoinbaseLiveReadOnlyAdapter,
    READ_ONLY_EXECUTION_SCOPE,
    UNKNOWN_DRAW_DOWN_REASON,
    load_coinbase_live_credentials,
)
from backend.runtime.coinbase_readiness import (
    evaluate_coinbase_live_read_only,
    merge_readiness_into_broker_state,
    selection_with_coinbase_readiness,
)
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


class FakeCoinbaseReadClient:
    def __init__(self, *, with_balance: bool = True) -> None:
        self.with_balance = with_balance
        self.calls: list[str] = []

    def get_accounts(self):
        self.calls.append("get_accounts")
        if not self.with_balance:
            return {"accounts": []}
        return {
            "accounts": [
                {
                    "currency": "CAD",
                    "available_balance": {"value": "20.00"},
                    "balance": {"value": "20.00"},
                }
            ]
        }

    def get_products(self):
        self.calls.append("get_products")
        return {"products": [{"product_id": "BTC-USD"}, {"product_id": "ETH-USD"}]}

    def get_time(self):
        self.calls.append("get_time")
        return {"iso": "2026-07-04T12:00:00Z"}

    def get_product_ticker(self, product_id: str):
        self.calls.append(f"get_product_ticker:{product_id}")
        return {"product_id": product_id, "price": "65000.00"}


class FakeCoinbaseSdk184ReadClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_accounts(self):
        self.calls.append("get_accounts")
        return {
            "accounts": [
                {
                    "currency": "USD",
                    "available_balance": {"value": "12.50"},
                    "hold": {"value": "0.00"},
                }
            ]
        }

    def get_products(self):
        self.calls.append("get_products")
        return {"products": [{"product_id": "BTC-USD"}]}

    def get_unix_time(self):
        self.calls.append("get_unix_time")
        return {"epoch_seconds": "1783180800", "iso": "2026-07-04T12:00:00Z"}

    def get_product(self, product_id: str):
        self.calls.append(f"get_product:{product_id}")
        return {"product_id": product_id, "price": "65000.00"}


def _env() -> dict[str, str]:
    return {
        "COINBASE_CDP_KEY_NAME": "organizations/hidden/apiKeys/secret-name",
        "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----hidden-----END PRIVATE KEY-----",
    }


def _coinbase_live_selection():
    return build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )


def test_phase153g_adapter_exposes_only_read_only_capabilities() -> None:
    public_methods = {
        name
        for name in dir(CoinbaseLiveReadOnlyAdapter)
        if not name.startswith("_") and callable(getattr(CoinbaseLiveReadOnlyAdapter, name))
    }

    assert {"authenticate", "get_account", "get_accounts", "get_balances", "get_products", "get_server_time", "get_ticker", "connection_status", "sync"} <= public_methods
    assert not any(fragment in name for name in public_methods for fragment in ("order", "cancel", "modify", "place", "submit"))


def test_phase153g_missing_credentials_fail_safely_without_secrets() -> None:
    adapter = CoinbaseLiveReadOnlyAdapter(env={})
    status = adapter.sync()
    payload = json.dumps(status)

    assert status["broker_connected"] is False
    assert status["broker_authenticated"] is False
    assert status["broker_execution_status"] == "DISABLED"
    assert status["can_live_execute"] is False
    assert status["credential_status"] == "MISSING"
    assert status["connection_error"] == "missing credentials"
    assert "PRIVATE KEY" not in payload
    assert "hidden" not in payload.lower()


def test_phase153g_successful_read_only_sync_sets_healthy_without_execution() -> None:
    adapter = CoinbaseLiveReadOnlyAdapter(
        env=_env(),
        read_client=FakeCoinbaseReadClient(),
        now=lambda: datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc),
    )
    status = adapter.sync()

    assert status["broker_connected"] is True
    assert status["broker_authenticated"] is True
    assert status["broker_health"] == "GREEN"
    assert status["execution_scope"] == READ_ONLY_EXECUTION_SCOPE
    assert status["broker_execution_status"] == "DISABLED"
    assert status["can_live_execute"] is False
    assert status["live_micro_pilot_state"] == "DISARMED"
    assert status["broker_guard"] == "REJECT_BEFORE_BROKER"
    assert status["account_equity"] == 20.0
    assert status["cash"] == 20.0
    assert status["available_balance"] == 20.0
    assert status["products_loaded"] == 2
    assert status["market_data_status"] == "OK"
    assert status["last_broker_sync"] == "2026-07-04T12:00:00+00:00"


def test_phase153g_sdk_184_server_time_method_is_supported() -> None:
    fake_client = FakeCoinbaseSdk184ReadClient()
    adapter = CoinbaseLiveReadOnlyAdapter(env=_env(), read_client=fake_client)

    server_time = adapter.get_server_time()
    status = adapter.sync()

    assert server_time["iso"] == "2026-07-04T12:00:00Z"
    assert "get_unix_time" in fake_client.calls
    assert status["read_checks"]["server_time"] == "OK"
    assert status["broker_authenticated"] is True
    assert status["execution_allowed"] is False
    assert status["broker_execution_armed"] is False


def test_phase153g_no_broker_balance_reports_unknown_drawdown() -> None:
    adapter = CoinbaseLiveReadOnlyAdapter(env=_env(), read_client=FakeCoinbaseReadClient(with_balance=False))
    status = adapter.sync()

    assert status["drawdown_status"] == "UNKNOWN"
    assert status["drawdown_reason"] == UNKNOWN_DRAW_DOWN_REASON
    assert status["account_equity"] is None


def test_phase153g_readiness_uses_canonical_adapter_and_preserves_disabled_execution() -> None:
    fake_client = FakeCoinbaseReadClient()
    status = evaluate_coinbase_live_read_only(
        _coinbase_live_selection(),
        env=_env(),
        adapter_factory=lambda: fake_client,
    )

    assert status["broker_connected"] is True
    assert status["broker_authenticated"] is True
    assert status["broker_health"] == "GREEN"
    assert status["auth_reason"] == "coinbase_read_only_authentication_verified"
    assert status["execution_scope"] == READ_ONLY_EXECUTION_SCOPE
    assert status["broker_execution_status"] == "DISABLED"
    assert status["can_live_execute"] is False
    assert all("order" not in call for call in fake_client.calls)


def test_phase153g_dashboard_exposes_read_only_broker_evidence_without_secret_values() -> None:
    status = evaluate_coinbase_live_read_only(
        _coinbase_live_selection(),
        env=_env(),
        adapter_factory=lambda: FakeCoinbaseReadClient(),
    )
    selection = selection_with_coinbase_readiness(_coinbase_live_selection(), status)
    broker_state = merge_readiness_into_broker_state(selection, status)
    frontend = build_frontend_payload({"broker_summary": broker_state})
    broker = frontend["sections"]["broker"]
    payload = json.dumps(frontend)

    assert broker["selected_broker"] == "COINBASE"
    assert broker["broker_connected"] is True
    assert broker["broker_authenticated"] is True
    assert broker["credential_status"] == "PRESENT"
    assert broker["connection_status"] == "GREEN"
    assert broker["last_broker_sync"] != "DATA UNAVAILABLE"
    assert broker["account_equity"] == 20.0
    assert broker["products_loaded"] == 2
    assert broker["execution_scope"] == READ_ONLY_EXECUTION_SCOPE
    assert broker["broker_execution_status"] == "DISABLED"
    assert broker["can_live_execute"] is False
    assert "PRIVATE KEY" not in payload
    assert "secret-name" not in payload


def test_phase153g_launcher_endpoint_and_mobile_page_render_read_only_status(tmp_path: Path, monkeypatch) -> None:
    artifacts = tmp_path / "artifacts"
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setattr(launcher.LauncherConfig, "ACCOUNT_STATE_FILE", str(account))
    monkeypatch.setattr(launcher.LauncherConfig, "SESSION_STATE_FILE", str(session))

    status = evaluate_coinbase_live_read_only(
        _coinbase_live_selection(),
        env=_env(),
        adapter_factory=lambda: FakeCoinbaseReadClient(),
    )
    selection = selection_with_coinbase_readiness(_coinbase_live_selection(), status)
    persist_broker_selection(
        account_state_path=account,
        session_state_path=session,
        selection=selection,
        broker_state_override=merge_readiness_into_broker_state(selection, status),
    )

    client = TestClient(launcher.app)
    endpoint = client.get("/api/v1/broker-read-only-status")
    page = client.get("/mobile")

    assert endpoint.status_code == 200
    data = endpoint.json()["data"]
    assert data["selected_broker"] == "COINBASE"
    assert data["broker_connected"] is True
    assert data["broker_execution_status"] == "DISABLED"
    assert data["can_live_execute"] is False
    assert page.status_code == 200
    assert "Last Broker Sync" in page.text
    assert "Account Equity" in page.text
    assert "Market Data Status" in page.text


def test_phase153g_no_coinbase_adapter_fallback_removed_and_credentials_redacted() -> None:
    balance = RealBalanceEngine("COINBASE", None).get_balance()
    credentials = load_coinbase_live_credentials(_env())
    payload = json.dumps(credentials.diagnostics())

    assert balance["source"] == "COINBASE_BALANCE_UNAVAILABLE"
    assert balance["source"] != "NO_COINBASE_ADAPTER"
    assert credentials.ready is True
    assert "hidden" not in payload
