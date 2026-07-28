from __future__ import annotations

import json
from pathlib import Path

from backend.runtime.broker_startup_selection import (
    broker_summary_from_artifacts,
    build_startup_broker_selection,
    live_readiness_broker_evidence,
    persist_broker_selection,
)
from backend.runtime.live_micro_pilot_governor import live_micro_pilot_status
from backend.validation.live_readiness_certification import certify_live_readiness
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_phase153b_startup_broker_selector_exists_before_execution_arming() -> None:
    source = Path("scripts/css_live_dashboard.py").read_text(encoding="utf-8")

    assert "=== CSS STARTUP BROKER SELECTION ===" in source
    assert "1. NONE / PAPER ONLY" in source
    assert "2. COINBASE" in source
    assert "3. OANDA" in source
    assert source.index("select_startup_broker_selection") < source.index("select_broker_execution_config")


def test_phase153b_missing_selection_defaults_to_none_paper_only() -> None:
    selection = build_startup_broker_selection()

    assert selection.selected_broker == "NONE"
    assert selection.broker_mode == "paper"
    assert selection.broker_execution_armed is False
    assert selection.broker_readiness_status == "BROKER_DISABLED"
    assert selection.as_dict()["execution_allowed"] is False


def test_phase153b_coinbase_live_can_be_selected_with_execution_disabled() -> None:
    selection = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )

    assert selection.selected_broker == "COINBASE"
    assert selection.broker_mode == "live"
    assert selection.broker_execution_armed is False
    assert selection.broker_execution_status == "DISABLED"
    assert selection.broker_connection_mode == "READ_ONLY_LIVE"
    assert selection.as_dict()["live_order_permission"] is False


def test_phase153b_selected_broker_persists_to_canonical_artifacts(tmp_path: Path) -> None:
    account = tmp_path / "artifacts" / "css_account_state_pcnrass.json"
    session = tmp_path / "artifacts" / "css_session_state_pcnrass.json"
    _write_json(account, {"account_balance": 1000.0})
    _write_json(session, {"session": {"engine_mode": "SAFE"}})
    selection = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )

    result = persist_broker_selection(
        account_state_path=account,
        session_state_path=session,
        selection=selection,
    )
    account_payload = json.loads(account.read_text(encoding="utf-8"))
    session_payload = json.loads(session.read_text(encoding="utf-8"))

    assert result["broker_state"]["selected_broker"] == "COINBASE"
    assert account_payload["selected_broker"] == "COINBASE"
    assert account_payload["broker_execution_enabled"] is False
    assert session_payload["session"]["broker_mode"] == "live"
    assert session_payload["session"]["broker_execution_status"] == "DISABLED"
    assert session_payload["session"]["execution_allowed"] is False


def test_phase153b_launcher_dashboard_shows_selected_broker_from_artifacts(tmp_path: Path, monkeypatch) -> None:
    artifacts = tmp_path / "artifacts"
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setattr(launcher.LauncherConfig, "ACCOUNT_STATE_FILE", str(account))
    monkeypatch.setattr(launcher.LauncherConfig, "SESSION_STATE_FILE", str(session))

    selection = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )
    persist_broker_selection(account_state_path=account, session_state_path=session, selection=selection)

    state = launcher.build_launcher_frontend_state()
    broker = state["sections"]["broker"]
    summary = state["sections"]["trade_summary"]

    assert broker["selected_broker"] == "COINBASE"
    assert broker["broker_mode"] == "live"
    assert broker["broker_execution_status"] == "DISABLED"
    assert broker["live_trading_enabled"] is False
    assert summary["broker"] == "COINBASE"
    assert summary["execution_allowed"] is False


def test_phase153b_live_readiness_clears_broker_blockers_only_with_read_only_evidence() -> None:
    missing = certify_live_readiness({})["blocker_summary"]["expected_operational_blocker_ids"]
    assert "broker_authentication_state" in missing
    assert "broker_health" in missing

    broker_summary = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
        broker_connected=True,
        broker_authenticated=True,
        broker_health="GREEN",
    ).as_dict()
    evidence = live_readiness_broker_evidence(broker_summary)
    report = certify_live_readiness(evidence)
    blocker_ids = {item["blocker_id"] for item in report["blocker_diagnostics"]}

    assert "broker_authentication_state" not in blocker_ids
    assert "broker_health" not in blocker_ids
    assert "unified_trade_gate" in blocker_ids
    assert report["execution_controls"]["live_execution_enabled"] is False
    assert report["audit"]["live_orders_submitted"] is False


def test_phase153b_no_broker_connectivity_evidence_does_not_clear_broker_blockers() -> None:
    broker_summary = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
        broker_connected=False,
        broker_authenticated=False,
    ).as_dict()
    report = certify_live_readiness(live_readiness_broker_evidence(broker_summary))
    blocker_ids = {item["blocker_id"] for item in report["blocker_diagnostics"]}

    assert "broker_authentication_state" in blocker_ids
    assert "broker_health" in blocker_ids


def test_phase153b_live_read_only_mode_does_not_arm_pilot_or_order_permission() -> None:
    selection = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
        broker_connected=True,
        broker_authenticated=True,
        broker_health="GREEN",
    )
    pilot = live_micro_pilot_status()

    assert selection.as_dict()["execution_allowed"] is False
    assert selection.broker_execution_status == "DISABLED"
    assert pilot["pilot_armed"] is False
    assert pilot["broker_submission_guard"] == "REJECT_BEFORE_BROKER"


def test_phase153b_paper_mode_behavior_remains_unchanged() -> None:
    payload = build_frontend_payload(
        {
            "broker_summary": broker_summary_from_artifacts({}, {"session": {"broker_mode": "paper"}}),
            "resolved_mode": "paper",
        }
    )

    assert payload["resolved_mode"] == "DISABLED"
    assert payload["sections"]["broker"]["selected_broker"] == "NONE"
    assert payload["sections"]["broker"]["broker_mode"] == "paper"
    assert payload["sections"]["broker"]["broker_execution_status"] == "DISABLED"
    assert payload["sections"]["runtime_status"]["execution_posture"] == "DISABLED"
