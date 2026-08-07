from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter
from backend.runtime.oanda_live_read_only_operational_validation import (
    FAILURE_REASONS,
    validate_oanda_live_read_only_operational,
)
from backend.runtime.oanda_readiness import (
    evaluate_oanda_live_read_only,
    selection_with_oanda_readiness,
    merge_readiness_into_broker_state as merge_oanda_readiness_into_broker_state,
)
from backend.runtime.broker_startup_selection import (
    build_startup_broker_selection,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


class FakeOandaReadClient:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def get_server_status(self):
        self.calls.append("get_server_status")
        if self.fail:
            raise self.fail
        return {"ok": True}

    def heartbeat(self):
        self.calls.append("heartbeat")
        return {"ok": True}

    def get_account_metadata(self):
        self.calls.append("get_account_metadata")
        return {"account_id": "test-acct", "currency": "USD"}

    def get_account_summary(self):
        self.calls.append("get_account_summary")
        return {"ok": True, "status": 200, "data": {"account": {"balance": "100.00", "NAV": "105.00"}}}

    def get_margin(self):
        self.calls.append("get_margin")
        return {"margin_used": 10.0, "margin_available": 90.0}

    def get_instruments(self):
        self.calls.append("get_instruments")
        return {"instruments": [{"name": "EUR_USD"}]}

    def get_pricing(self):
        self.calls.append("get_pricing")
        return {"prices": [{"instrument": "EUR_USD", "closeoutBid": "1.1"}]}

    def get_candles(self, instrument="EUR_USD"):
        self.calls.append("get_candles")
        return {"candles": [{"time": "2026-07-05T12:00:00Z"}]}

    def get_open_positions(self):
        self.calls.append("get_open_positions")
        return {"positions": []}

    def get_open_trades(self):
        self.calls.append("get_open_trades")
        return {"trades": []}

    def place_order(self, *args, **kwargs):
        raise AssertionError("read-only validation must never submit orders")

    def submit_order(self, *args, **kwargs):
        raise AssertionError("read-only validation must never submit orders")


def _env() -> dict[str, str]:
    return {
        "OANDA_API_KEY": "test-key",
        "OANDA_ACCOUNT_ID": "test-acct",
        "OANDA_BASE_URL": "https://api-fxtrade.oanda.com",
    }


def _adapter(client: FakeOandaReadClient) -> OandaLiveReadOnlyAdapter:
    return OandaLiveReadOnlyAdapter(
        env=_env(),
        read_client=client,
        now=lambda: datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
    )


def test_phase155b_missing_credentials_fail_closed_and_publish_artifacts(tmp_path) -> None:
    result = validate_oanda_live_read_only_operational(
        adapter_factory=lambda: OandaLiveReadOnlyAdapter(env={}),
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


def test_phase155b_successful_read_only_validation_uses_existing_adapter_only(tmp_path) -> None:
    client = FakeOandaReadClient()
    result = validate_oanda_live_read_only_operational(
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
    assert "place_order" not in client.calls
    assert "submit_order" not in client.calls


def test_phase155b_structured_failure_reasons_are_classified(tmp_path) -> None:
    client = FakeOandaReadClient(fail=TimeoutError("request timeout"))
    result = validate_oanda_live_read_only_operational(
        adapter_factory=lambda: _adapter(client),
        artifacts_dir=tmp_path,
    )

    reasons = {item["reason"] for item in result["failure_reasons"]}
    assert "TIMEOUT" in reasons
    assert reasons <= set(FAILURE_REASONS)
    assert result["execution_allowed"] is False


def test_phase155b_frontend_and_api_display_validation_status() -> None:
    validation = {
        "broker_validation": {
            "validation_status": "PASS",
            "api_reachable": True,
            "authentication": True,
            "account_loaded": True,
            "portfolio_loaded": True,
            "balances_loaded": True,
            "products_loaded": 1,
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
            "selected_broker": "OANDA",
            "oanda_live_validation": validation,
        }
    )

    frontend = build_frontend_payload(state)
    section = frontend["sections"]["oanda_live_validation"]
    assert section["api_reachable"] is True
    assert section["authentication"] is True
    assert section["account_loaded"] is True
    assert section["balances_loaded"] is True
    assert section["products_loaded"] == 1
    assert section["market_data_loaded"] is True
    assert section["execution_allowed"] is False

    response = TestClient(create_app(lambda: state)).get("/api/v1/oanda-live-read-only-validation")
    assert response.status_code == 200
    assert response.json()["section"] == "oanda_live_validation"
    assert response.json()["data"]["validation_status"] == "PASS"


def test_phase155b_launcher_reads_artifacts_and_displays_panel(monkeypatch, tmp_path) -> None:
    validate_oanda_live_read_only_operational(
        adapter_factory=lambda: _adapter(FakeOandaReadClient()),
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
    response = client.get("/api/v1/oanda-live-read-only-validation")
    assert response.status_code == 200
    assert response.json()["data"]["validation_status"] == "PASS"
    assert response.json()["data"]["broker_execution_status"] == "DISABLED"
    assert response.json()["data"]["execution_authority"] is False

    page = client.get("/mobile")
    assert page.status_code == 200
    assert "OANDA Validation" in page.text
    assert "OANDA API Reachable" in page.text
    assert "OANDA Market Data Loaded" in page.text


def test_phase155b_safety_evaluations_locked() -> None:
    selection = build_startup_broker_selection(
        selected_broker="OANDA",
        broker_mode="live",
        broker_execution_armed=False,
        operator_requested_live=True,
    )
    readiness = evaluate_oanda_live_read_only(selection, env=_env(), adapter_factory=FakeOandaReadClient)
    
    assert readiness["execution_allowed"] is False
    assert readiness["can_live_execute"] is False
    assert readiness["execution_authority"] is False
    assert readiness["live_micro_pilot_state"] == "DISARMED"
    assert readiness["broker_guard"] == "REJECT_BEFORE_BROKER"
    assert readiness["live_authority_state"] == "BLOCKED"
    assert readiness["read_only_ready"] is True
    assert readiness["execution_ready"] is False
    assert readiness["live_execution_ready"] is False
    assert readiness["live_execution_blocked"] is True
    assert readiness["preflight_blocker_ids"] == [
        "BLK-OANDA-LIVE",
        "BLK-FX-CONVERSION",
        "BLK-ANTIBLEED-CAD20",
    ]
