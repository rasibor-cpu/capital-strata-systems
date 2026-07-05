from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.runtime.broker_startup_selection import (
    build_startup_broker_selection,
    persist_broker_selection,
)
from backend.runtime.coinbase_readiness import (
    evaluate_coinbase_live_read_only,
    merge_readiness_into_broker_state,
    selection_with_coinbase_readiness,
)
from backend.runtime.startup_summary import (
    build_live_startup_summary,
    format_live_startup_summary,
    publish_startup_diagnostics,
)
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


class FakeReadClient:
    def get_accounts(self):
        return {"accounts": [{"available_balance": {"value": "20.00"}, "balance": {"value": "20.00"}}]}

    def get_products(self):
        return {"products": [{"product_id": "BTC-USD"}]}

    def get_time(self):
        return {"iso": "2026-07-04T12:00:00Z"}

    def get_product_ticker(self, product_id: str):
        return {"product_id": product_id, "price": "65000.00"}


def _env() -> dict[str, str]:
    return {"COINBASE_CDP_KEY_NAME": "present", "COINBASE_CDP_PRIVATE_KEY": "present"}


def _readiness_state() -> dict[str, object]:
    selection = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )
    readiness = evaluate_coinbase_live_read_only(selection, env=_env(), adapter_factory=lambda: FakeReadClient())
    selection = selection_with_coinbase_readiness(selection, readiness)
    return merge_readiness_into_broker_state(selection, readiness)


def test_phase153h_startup_summary_reflects_final_read_only_state() -> None:
    broker_state = _readiness_state()
    summary = build_live_startup_summary(
        {
            "selected_broker": "COINBASE",
            "broker_mode": "live",
            "broker_execution_armed": False,
            "can_live_execute": False,
            "execution_scope": "LIVE READ-ONLY VALIDATION",
        },
        broker_status=broker_state,
        pilot_status={"pilot_state": "DISARMED", "canonical_live_pilot_limit_cad": "20.00", "currency": "CAD"},
    )
    lines = format_live_startup_summary(summary)

    assert lines[0] == "========== LIVE STARTUP SUMMARY =========="
    assert lines[-1] == "========================================="
    assert "Broker Execution: DISABLED" in lines
    assert "Can Live Execute: NO" in lines
    assert summary["Broker"] == "COINBASE"
    assert summary["Readiness State"] == "READ_ONLY_READY"
    assert summary["GO / NO GO"] == "GO"
    assert summary["startup_diagnostics"]["execution_enabled"] is False
    assert summary["startup_diagnostics"]["can_live_execute"] is False


def test_phase153h_startup_summary_never_displays_armed_when_execution_not_armed() -> None:
    broker_state = {**_readiness_state(), "broker_execution_armed": False, "can_live_execute": False}
    summary = build_live_startup_summary(
        {"selected_broker": "COINBASE", "broker_mode": "live", "broker_execution_armed": False},
        broker_status=broker_state,
        pilot_status={"pilot_state": "DISARMED"},
    )

    assert summary["Broker Execution"] == "DISABLED"
    assert summary["broker_execution_status"] == "DISABLED"
    assert summary["Can Live Execute"] == "NO"
    assert summary["can_live_execute"] is False


def test_phase153h_dashboard_and_launcher_expose_checklist_and_diagnostics(tmp_path: Path, monkeypatch) -> None:
    artifacts = tmp_path / "artifacts"
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setattr(launcher.LauncherConfig, "ACCOUNT_STATE_FILE", str(account))
    monkeypatch.setattr(launcher.LauncherConfig, "SESSION_STATE_FILE", str(session))

    broker_state = _readiness_state()
    selection = build_startup_broker_selection(selected_broker="COINBASE", broker_mode="live", broker_execution_armed=False)
    persist_broker_selection(
        account_state_path=account,
        session_state_path=session,
        selection=selection,
        broker_state_override=broker_state,
    )
    frontend = build_frontend_payload({"broker_summary": broker_state})
    broker = frontend["sections"]["broker"]
    client = TestClient(launcher.app)
    endpoint = client.get("/api/v1/live-readiness-state")
    page = client.get("/mobile")

    assert broker["readiness_state"] == "READ_ONLY_READY"
    assert broker["go_no_go"] == "GO"
    assert broker["startup_diagnostics"]["broker"] == "COINBASE"
    assert endpoint.status_code == 200
    assert endpoint.json()["data"]["readiness_state"] == "READ_ONLY_READY"
    assert page.status_code == 200
    assert "Readiness Checklist" in page.text
    assert "Readiness State" in page.text


def test_phase153h_startup_diagnostics_json_is_canonical(tmp_path: Path) -> None:
    path = tmp_path / "startup_diagnostics.json"
    summary = build_live_startup_summary(
        {"selected_broker": "COINBASE", "broker_mode": "live", "broker_execution_armed": False},
        broker_status=_readiness_state(),
        pilot_status={"pilot_state": "DISARMED"},
    )
    diagnostics = publish_startup_diagnostics(path, summary)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert diagnostics["broker"] == "COINBASE"
    assert loaded["execution_enabled"] is False
    assert loaded["can_live_execute"] is False
    assert loaded["broker_guard"] == "REJECT_BEFORE_BROKER"
