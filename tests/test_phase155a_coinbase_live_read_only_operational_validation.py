from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.runtime.coinbase_live_adapter import CoinbaseLiveReadOnlyAdapter
from backend.runtime.coinbase_live_read_only_operational_validation import (
    FAILURE_REASONS,
    validate_coinbase_live_read_only_operational,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


class FakeCoinbaseReadClient:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def get_time(self):
        self.calls.append("get_time")
        if self.fail:
            raise self.fail
        return {"iso": "2026-07-05T12:00:00Z"}

    def get_accounts(self):
        self.calls.append("get_accounts")
        return {"accounts": [{"uuid": "acct", "available_balance": {"value": "100.00", "currency": "CAD"}}]}

    def get_portfolios(self):
        self.calls.append("get_portfolios")
        return {"portfolios": [{"uuid": "portfolio"}]}

    def get_products(self):
        self.calls.append("get_products")
        return {"products": [{"product_id": "BTC-USD"}]}

    def get_product_ticker(self, product_id: str):
        self.calls.append(f"get_product_ticker:{product_id}")
        return {"product_id": product_id, "price": "100000.00"}

    def create_order(self):
        raise AssertionError("live read-only validation must never submit orders")

    def cancel_order(self):
        raise AssertionError("live read-only validation must never cancel orders")


def _env() -> dict[str, str]:
    return {
        "COINBASE_CDP_KEY_NAME": "organizations/test/apiKeys/test",
        "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----redacted-----END PRIVATE KEY-----",
    }


def _adapter(client: FakeCoinbaseReadClient) -> CoinbaseLiveReadOnlyAdapter:
    return CoinbaseLiveReadOnlyAdapter(
        env=_env(),
        read_client=client,
        now=lambda: datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
    )


def test_phase155a_missing_credentials_fail_closed_and_publish_artifacts(tmp_path) -> None:
    result = validate_coinbase_live_read_only_operational(
        adapter_factory=lambda: CoinbaseLiveReadOnlyAdapter(env={}),
        artifacts_dir=tmp_path,
        now=lambda: datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
    )

    assert result["validation_status"] == "FAIL_CLOSED"
    assert result["api_reachable"] is False
    assert result["execution_allowed"] is False
    assert result["broker_execution_status"] == "DISABLED"
    assert result["execution_authority"] is False
    assert result["can_live_execute"] is False
    assert result["live_micro_pilot_state"] == "DISARMED"
    assert result["failure_reasons"][0]["reason"] == "MISSING_CREDENTIALS"
    assert (tmp_path / "broker_validation.json").exists()
    assert (tmp_path / "broker_health.json").exists()
    assert (tmp_path / "broker_market_snapshot.json").exists()


def test_phase155a_successful_read_only_validation_uses_existing_adapter_only(tmp_path) -> None:
    client = FakeCoinbaseReadClient()
    result = validate_coinbase_live_read_only_operational(
        adapter_factory=lambda: _adapter(client),
        artifacts_dir=tmp_path,
        now=lambda: datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
    )

    assert result["validation_status"] == "PASS"
    assert result["api_reachable"] is True
    assert result["authenticated"] is True
    assert result["account_loaded"] is True
    assert result["portfolio_loaded"] is True
    assert result["balances_loaded"] is True
    assert result["products_loaded"] == 1
    assert result["market_data_loaded"] is True
    assert result["last_successful_sync"] == "2026-07-05T12:00:00+00:00"
    assert "create_order" not in client.calls
    assert "cancel_order" not in client.calls


def test_phase155a_structured_failure_reasons_are_classified(tmp_path) -> None:
    client = FakeCoinbaseReadClient(fail=TimeoutError("request timeout"))
    result = validate_coinbase_live_read_only_operational(
        adapter_factory=lambda: _adapter(client),
        artifacts_dir=tmp_path,
    )

    reasons = {item["reason"] for item in result["failure_reasons"]}
    assert "TIMEOUT" in reasons
    assert reasons <= set(FAILURE_REASONS)
    assert result["execution_allowed"] is False


def test_phase155a_frontend_and_api_display_validation_status() -> None:
    validation = {
        "broker_validation": {
            "validation_status": "PASS",
            "api_reachable": True,
            "authentication": True,
            "account_loaded": True,
            "portfolio_loaded": True,
            "balances_loaded": True,
            "products_loaded": 4,
            "market_data_loaded": True,
            "last_successful_sync": "2026-07-05T12:00:00+00:00",
            "validation_timestamp": "2026-07-05T12:00:00+00:00",
            "failure_reasons": [],
        },
        "broker_health": {"last_successful_sync": "2026-07-05T12:00:00+00:00"},
        "broker_market_snapshot": {"validation_timestamp": "2026-07-05T12:00:00+00:00"},
    }
    state = DashboardHydrationCoordinator().hydrate(
        broker_payload={
            "selected_broker": "COINBASE",
            "coinbase_live_validation": validation,
        }
    )

    frontend = build_frontend_payload(state)
    section = frontend["sections"]["coinbase_live_validation"]
    assert section["api_reachable"] is True
    assert section["authentication"] is True
    assert section["account_loaded"] is True
    assert section["balances_loaded"] is True
    assert section["products_loaded"] == 4
    assert section["market_data_loaded"] is True
    assert section["execution_allowed"] is False

    response = TestClient(create_app(lambda: state)).get("/api/v1/coinbase-live-read-only-validation")
    assert response.status_code == 200
    assert response.json()["section"] == "coinbase_live_validation"
    assert response.json()["data"]["validation_status"] == "PASS"


def test_phase155a_launcher_reads_artifacts_and_displays_panel(monkeypatch, tmp_path) -> None:
    validate_coinbase_live_read_only_operational(
        adapter_factory=lambda: _adapter(FakeCoinbaseReadClient()),
        artifacts_dir=tmp_path,
        now=lambda: datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setattr(
        launcher,
        "ensure_runtime_artifacts_current",
        lambda *args, **kwargs: {"freshness": {"artifacts": {"account_state": {"freshness": "GREEN"}}}},
    )

    client = TestClient(launcher.app)
    response = client.get("/api/v1/coinbase-live-read-only-validation")
    assert response.status_code == 200
    assert response.json()["data"]["validation_status"] == "PASS"
    assert response.json()["data"]["broker_execution_status"] == "DISABLED"
    assert response.json()["data"]["execution_authority"] is False

    page = client.get("/mobile")
    assert page.status_code == 200
    assert "Coinbase Validation" in page.text
    assert "API Reachable" in page.text
    assert "Market Data Loaded" in page.text
