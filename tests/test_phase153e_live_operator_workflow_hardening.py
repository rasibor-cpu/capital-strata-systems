from __future__ import annotations

import json
from pathlib import Path

from backend.runtime.broker_startup_selection import (
    broker_summary_from_artifacts,
    build_startup_broker_selection,
    persist_broker_selection,
)
from backend.runtime.coinbase_readiness import (
    evaluate_coinbase_live_read_only,
    merge_readiness_into_broker_state,
    selection_with_coinbase_readiness,
)
from backend.runtime.live_operator_wizard import (
    LIVE_OPERATOR_WIZARD_SEQUENCE,
    StartupWizardState,
    broker_validation_display,
    build_startup_summary,
    choose_broker,
    choose_broker_execution_arming,
    choose_broker_mode,
    choose_global_mode,
    paper_live_environment_conflict,
    set_cycle_mode,
    set_engine_mode,
    startup_summary_confirmation,
)
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


def test_phase153e_startup_wizard_order_is_deterministic() -> None:
    assert LIVE_OPERATOR_WIZARD_SEQUENCE == (
        "authentication",
        "global_mode_selection",
        "global_live_confirmation",
        "broker_selection",
        "broker_specific_mode_selection",
        "broker_live_read_only_confirmation",
        "broker_execution_arming",
        "engine_mode_selection",
        "cycle_mode_selection",
        "startup_summary_confirmation",
        "start_runtime_cycle",
    )


def test_phase153e_invalid_live_confirmation_does_not_advance() -> None:
    state = StartupWizardState(step="global_mode_selection")
    result = choose_global_mode(state, "2", "2")

    assert result.advanced is False
    assert result.state.step == "global_live_confirmation"
    assert "INVALID CONFIRMATION" in result.error
    assert "Expected: LIVE" in result.error
    assert "Received: 2" in result.error


def test_phase153e_broker_selection_cannot_be_skipped() -> None:
    state = StartupWizardState(step="broker_selection")
    result = choose_broker(state, "")

    assert result.advanced is False
    assert result.state.selected_broker == ""
    assert result.state.step == "broker_selection"


def test_phase153e_execution_cannot_be_armed_with_broker_none() -> None:
    state = StartupWizardState(selected_broker="NONE", broker_mode="paper", step="broker_execution_arming")
    result = choose_broker_execution_arming(
        state,
        "2",
        role_profile={"can_arm_broker": True},
    )

    assert result.advanced is False
    assert result.state.broker_execution_armed is False
    assert result.state.step == "broker_selection"
    assert "Broker execution cannot be armed because no broker is selected." in result.error


def test_phase153e_arm_live_requires_second_confirmation() -> None:
    state = StartupWizardState(
        selected_broker="COINBASE",
        broker_mode="live",
        step="broker_execution_arming",
    )
    result = choose_broker_execution_arming(
        state,
        "2",
        arm_confirmation="ARM LIVE",
        role_profile={"can_arm_broker": True},
    )

    assert result.advanced is True
    assert result.state.broker_execution_armed is True
    assert result.state.can_live_execute is True


def test_phase153e_wrong_arm_live_confirmation_leaves_execution_disabled() -> None:
    state = StartupWizardState(
        selected_broker="COINBASE",
        broker_mode="live",
        step="broker_execution_arming",
    )
    result = choose_broker_execution_arming(
        state,
        "2",
        arm_confirmation="LIVE",
        role_profile={"can_arm_broker": True},
    )

    assert result.state.broker_execution_armed is False
    assert result.state.can_live_execute is False
    assert "Expected: ARM LIVE" in result.error


def test_phase153e_paper_mode_cannot_use_live_broker_environment() -> None:
    conflict = paper_live_environment_conflict(
        "OANDA",
        "paper",
        env={"OANDA_ENV": "live", "OANDA_API_KEY": "redacted", "OANDA_ACCOUNT_ID": "redacted"},
    )
    state = StartupWizardState(
        global_mode="paper",
        selected_broker="OANDA",
        step="broker_specific_mode_selection",
    )
    result = choose_broker_mode(
        state,
        "1",
        env={"OANDA_ENV": "live"},
    )

    assert conflict["blocking"] is True
    assert "OANDA_ENV" in conflict["live_environment_keys"]
    assert "Paper mode cannot use LIVE broker credentials/environment." in conflict["message"]
    assert result.advanced is False
    assert result.state.step == "broker_specific_mode_selection"


def test_phase153e_startup_summary_reflects_actual_runtime_state() -> None:
    state = StartupWizardState(
        global_mode="live",
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
        engine_mode="SAFE",
        cycle_mode="manual",
        execution_scope="LIVE READ-ONLY VALIDATION",
        can_live_execute=False,
    )
    summary = build_startup_summary(
        state,
        broker_status={"connection_status": "NOT_TESTED", "auth_status": "NOT_TESTED"},
        pilot_status={"pilot_state": "DISARMED", "currency": "CAD", "canonical_live_pilot_limit_cad": "20.00"},
    )
    decision = startup_summary_confirmation(state, "N")

    assert summary["global_mode"] == "live"
    assert summary["selected_broker"] == "COINBASE"
    assert summary["broker_execution_status"] == "DISABLED"
    assert summary["canonical_live_capital_authority"] == "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR"
    assert summary["canonical_pilot_cap"] == "CAD 20.00"
    assert summary["can_live_execute"] is False
    assert decision.state.restart_requested is True


def test_phase153e_coinbase_live_read_only_execution_disabled_remains_order_blocked() -> None:
    selection = build_startup_broker_selection(
        selected_broker="COINBASE",
        broker_mode="live",
        broker_execution_armed=False,
    )
    readiness = evaluate_coinbase_live_read_only(selection, env={})
    status = broker_validation_display(
        selected_broker="COINBASE",
        broker_mode="live",
        readiness={**readiness, "broker_execution_armed": False},
    )

    assert readiness["can_live_execute"] is False
    assert readiness["live_order_permission"] is False
    assert status["credential_status"] == "MISSING"
    assert status["order_submission_status"] == "DISABLED"
    assert status["orders_sent_count"] == 0


def test_phase153e_dashboard_exposes_hardened_broker_status(tmp_path: Path, monkeypatch) -> None:
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
    readiness = evaluate_coinbase_live_read_only(selection, env={})
    readiness.update(
        broker_validation_display(
            selected_broker="COINBASE",
            broker_mode="live",
            readiness=readiness,
        )
    )
    selection = selection_with_coinbase_readiness(selection, readiness)
    persist_broker_selection(
        account_state_path=account,
        session_state_path=session,
        selection=selection,
        broker_state_override=merge_readiness_into_broker_state(selection, readiness),
    )
    summary = broker_summary_from_artifacts(
        json.loads(account.read_text(encoding="utf-8")),
        json.loads(session.read_text(encoding="utf-8")),
    )
    frontend = build_frontend_payload({"broker_summary": summary})
    launcher_state = launcher.build_launcher_frontend_state()

    broker = frontend["sections"]["broker"]
    assert broker["selected_broker"] == "COINBASE"
    assert broker["credential_status"] == "MISSING"
    assert broker["auth_status"] == "NOT_TESTED"
    assert broker["connection_status"] == "NOT_TESTED"
    assert broker["order_submission_status"] == "DISABLED"
    assert broker["orders_sent_count"] == 0
    assert broker["canonical_live_capital_authority"] == "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR"
    assert launcher_state["sections"]["broker"]["orders_blocked_count"] == 0


def test_phase153e_existing_paper_mode_still_works() -> None:
    state = StartupWizardState(step="global_mode_selection")
    global_result = choose_global_mode(state, "1")
    broker_result = choose_broker(global_result.state, "1")
    arm_result = choose_broker_execution_arming(
        broker_result.state,
        "1",
        role_profile={"can_arm_broker": True},
    )
    engine_result = set_engine_mode(arm_result.state, "SAFE")
    cycle_result = set_cycle_mode(engine_result.state, "manual")

    assert cycle_result.state.global_mode == "paper"
    assert cycle_result.state.selected_broker == "NONE"
    assert cycle_result.state.broker_mode == "paper"
    assert cycle_result.state.broker_execution_armed is False
    assert cycle_result.state.cycle_mode == "manual"
