from __future__ import annotations

import builtins
import inspect
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dashboard.runtime import web_kill_switch_governance
from dashboard.runtime.web_kill_switch_governance import (
    ACTION_ENGAGE,
    ACTION_REQUEST_RELEASE,
    DECISION_APPROVED,
    DECISION_BLOCKED,
    DECISION_INVALID,
    DECISION_PENDING_CONFIRMATION,
    DECISION_REJECTED,
    WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
    build_kill_switch_audit_preview,
    build_web_kill_switch_status_payload,
    engage_web_kill_switch,
    evaluate_web_kill_switch_governance_request,
)

GENERATED_AT = "2026-07-29T00:00:00+00:00"


def _confirmation(action: str = ACTION_ENGAGE, token: str | None = None) -> dict[str, Any]:
    return {
        "confirmed": True,
        "action": action,
        "token": token or WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
    }


def _request(**overrides: Any) -> dict[str, Any]:
    payload = {
        "action": ACTION_ENGAGE,
        "request_id": "REQ-183G-F-001",
        "operator_id": "operator.alpha",
        "reason": "operator requested emergency block",
        "confirmation": _confirmation(),
        "source_channel": "web",
        "correlation_id": "CORR-1",
    }
    payload.update(overrides)
    return payload


def _release_request(**overrides: Any) -> dict[str, Any]:
    payload = _request(
        action=ACTION_REQUEST_RELEASE,
        request_id="REQ-183G-F-REL-001",
        reason="operator requested governed release review",
        confirmation={
            "confirmed": True,
            "action": ACTION_REQUEST_RELEASE,
            "token": "REQUEST_KILL_SWITCH_RELEASE",
        },
    )
    payload.update(overrides)
    return payload


def _canonical_release(**overrides: Any) -> dict[str, Any]:
    payload = {
        "engaged": True,
        "release_review_state": "RELEASE_REVIEW_PERMITTED",
        "readiness_status": "GREEN",
        "certification_status": "CERTIFIED",
        "incident_status": "CLEARED",
        "application_confirmed": False,
    }
    payload.update(overrides)
    return payload


def test_import_succeeds_with_no_side_effects(tmp_path: Path) -> None:
    marker = tmp_path / "kill-switch-state.json"

    assert web_kill_switch_governance.WEB_KILL_SWITCH_GOVERNANCE_VERSION == (
        "css.web_kill_switch_governance.v2"
    )
    assert not marker.exists()


def test_valid_engage_builds_governance_envelope_without_application_claim() -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _request(),
        generated_at_utc=GENERATED_AT,
    )

    assert payload["governance_decision"] == DECISION_APPROVED
    assert payload["canonical_application_status"] == "UNCONFIRMED"
    assert payload["canonical_effective_state"] == "UNAVAILABLE"
    assert payload["orders_enabled"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["effective_state_changed"] is False
    assert payload["audit_recorded"] is False


@pytest.mark.parametrize(
    ("overrides", "expected_decision", "expected_blocker"),
    [
        ({"action": ""}, DECISION_INVALID, "action_missing"),
        ({"action": "ENABLE_TRADING"}, DECISION_INVALID, "action_unsupported"),
        ({"operator_id": None}, DECISION_REJECTED, "operator_id_missing"),
        ({"operator_id": "   "}, DECISION_REJECTED, "operator_id_missing"),
        ({"reason": None}, DECISION_REJECTED, "reason_missing"),
        ({"reason": "   "}, DECISION_REJECTED, "reason_missing"),
        ({"confirmation": None}, DECISION_PENDING_CONFIRMATION, "confirmation_missing"),
        (
            {"confirmation": {"confirmed": "true", "action": ACTION_ENGAGE, "token": WEB_KILL_SWITCH_CONFIRMATION_TOKEN}},
            DECISION_REJECTED,
            "confirmation_boolean_invalid",
        ),
        (
            {"confirmation": {"confirmed": True, "action": ACTION_REQUEST_RELEASE, "token": WEB_KILL_SWITCH_CONFIRMATION_TOKEN}},
            DECISION_REJECTED,
            "confirmation_action_mismatch",
        ),
        ({"request_id": ""}, DECISION_REJECTED, "request_id_missing"),
    ],
)
def test_invalid_request_controls(
    overrides: dict[str, Any],
    expected_decision: str,
    expected_blocker: str,
) -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _request(**overrides),
        generated_at_utc=GENERATED_AT,
    )

    assert payload["governance_decision"] == expected_decision
    assert expected_blocker in payload["blocking_reasons"]
    assert payload["orders_enabled"] is False


def test_deterministic_timestamp_and_request_id_injection() -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _request(request_id=""),
        generated_at_utc=GENERATED_AT,
        request_id="REQ-INJECTED-001",
    )

    assert payload["request_id"] == "REQ-INJECTED-001"
    assert payload["created_at_utc"] == GENERATED_AT
    assert payload["evaluated_at_utc"] == GENERATED_AT
    assert payload["governance_decision"] == DECISION_APPROVED


def test_duplicate_identical_request_is_deterministic() -> None:
    request = _request()
    first = evaluate_web_kill_switch_governance_request(
        request,
        duplicate_context={"request": request},
        generated_at_utc=GENERATED_AT,
    )
    second = evaluate_web_kill_switch_governance_request(
        request,
        duplicate_context={"request": request},
        generated_at_utc=GENERATED_AT,
    )

    assert first == second
    assert first["governance_decision"] == DECISION_APPROVED


def test_conflicting_duplicate_request_id_is_rejected() -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _request(reason="operator requested emergency block"),
        duplicate_context={
            "request": _request(reason="different governed reason")
        },
        generated_at_utc=GENERATED_AT,
    )

    assert payload["governance_decision"] == DECISION_REJECTED
    assert "duplicate_request_id_conflict" in payload["blocking_reasons"]


def test_engage_compatibility_api_does_not_mutate_authority() -> None:
    payload = engage_web_kill_switch(
        operator_id="operator.alpha",
        confirmation_token=WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
        reason="operator requested emergency block",
        generated_at_utc=GENERATED_AT,
        request_id="REQ-ENGAGE-COMPAT",
    )

    assert payload["governance_decision"] == DECISION_APPROVED
    assert payload["orders_enabled"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["effective_state_changed"] is False
    assert payload["source_metadata"]["no_filesystem_writes"] is True


def test_release_blocks_without_supplied_canonical_release_authority() -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _release_request(),
        generated_at_utc=GENERATED_AT,
    )

    assert payload["governance_decision"] == DECISION_BLOCKED
    assert "canonical_release_authority_missing" in payload["blocking_reasons"]
    assert payload["effective_state_changed"] is False


@pytest.mark.parametrize(
    ("canonical", "expected_blocker"),
    [
        ({"runtime_mode": "LIVE"}, "release_review_not_permitted"),
        ({"broker_ready": True}, "release_review_not_permitted"),
        ({"mobile_controls": {"requested_orders_enabled": True}}, "release_review_not_permitted"),
        ({"ui_state": "CLEAR"}, "release_review_not_permitted"),
        ({"elapsed_seconds": 999999}, "release_review_not_permitted"),
        (_canonical_release(certification_status="UNKNOWN"), "certification_not_passed"),
        (_canonical_release(readiness_status="FAILED"), "readiness_not_passed"),
        (_canonical_release(incident_status="ACTIVE"), "blocking_incident_active"),
        (_canonical_release(contradictory=True), "canonical_state_contradictory"),
        (_canonical_release(malformed=True), "canonical_state_malformed"),
    ],
)
def test_release_safety_blockers(canonical: dict[str, Any], expected_blocker: str) -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _release_request(),
        canonical_state=canonical,
        generated_at_utc=GENERATED_AT,
    )

    assert payload["governance_decision"] == DECISION_BLOCKED
    assert expected_blocker in payload["blocking_reasons"]
    assert payload["canonical_application_status"] == "UNCONFIRMED"
    assert payload["effective_state_changed"] is False


def test_release_with_full_canonical_review_is_only_approved_for_processing() -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _release_request(),
        canonical_state=_canonical_release(),
        generated_at_utc=GENERATED_AT,
    )

    assert payload["governance_decision"] == DECISION_APPROVED
    assert payload["canonical_effective_state"] == "ENGAGED"
    assert payload["canonical_application_status"] == "UNCONFIRMED"
    assert payload["effective_state_changed"] is False
    assert payload["orders_enabled"] is False


def test_no_automatic_reset_in_status_or_audit_preview() -> None:
    status = build_web_kill_switch_status_payload(generated_at_utc=GENERATED_AT)
    preview = build_kill_switch_audit_preview(generated_at_utc=GENERATED_AT)

    assert status["engaged"] is True
    assert status["canonical_application_status"] == "UNCONFIRMED"
    assert preview["effective_state_changed"] is False
    assert preview["audit_recorded"] is False


def test_sensitive_fields_are_rejected_and_not_returned() -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _request(api_key="SECRET", reason="operator requested emergency block"),
        generated_at_utc=GENERATED_AT,
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["governance_decision"] == DECISION_REJECTED
    assert "sensitive_payload_rejected" in payload["blocking_reasons"]
    assert "SECRET" not in serialized


def test_absolute_paths_are_not_exposed() -> None:
    payload = evaluate_web_kill_switch_governance_request(
        _request(source_path="C:\\rasib\\source\\capital-strata-systems\\runtime\\kill.switch"),
        generated_at_utc=GENERATED_AT,
    )

    assert "C:\\rasib" not in json.dumps(payload, sort_keys=True)


def test_output_ordering_and_serialization_are_deterministic() -> None:
    first = evaluate_web_kill_switch_governance_request(
        _request(),
        generated_at_utc=GENERATED_AT,
    )
    second = evaluate_web_kill_switch_governance_request(
        _request(),
        generated_at_utc=GENERATED_AT,
    )

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["governance_hash"] == second["governance_hash"]


def test_no_filesystem_env_network_subprocess_broker_order_or_store_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_side_effect(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("web kill-switch governance attempted a prohibited side effect")

    with monkeypatch.context() as guard:
        guard.setattr(os, "getenv", fail_side_effect)
        guard.setattr(os, "putenv", fail_side_effect)
        guard.setattr(os, "system", fail_side_effect)
        guard.setattr(socket, "socket", fail_side_effect)
        guard.setattr(socket, "create_connection", fail_side_effect)
        guard.setattr(subprocess, "run", fail_side_effect)
        guard.setattr(subprocess, "Popen", fail_side_effect)
        guard.setattr(Path, "open", fail_side_effect)
        guard.setattr(Path, "read_text", fail_side_effect)
        guard.setattr(Path, "write_text", fail_side_effect)
        guard.setattr(builtins, "open", fail_side_effect)

        payload = evaluate_web_kill_switch_governance_request(
            _request(),
            generated_at_utc=GENERATED_AT,
        )

    assert payload["governance"]["audit_persistence_enabled"] is False
    assert payload["governance"]["mobile_control_mutation_allowed"] is False
    assert payload["source_metadata"]["no_environment_reads"] is True
    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_placement"] is True


def test_source_does_not_import_hold_files_or_authority_call_paths() -> None:
    source = inspect.getsource(web_kill_switch_governance)

    assert "dashboard.runtime.css_mobile_controls" not in source
    assert "dashboard.runtime.web_kill_switch_governance" not in source.replace(
        '"dashboard.runtime.web_kill_switch_governance"', ""
    )
    assert "operator_action_audit_ledger" not in source
    assert "evaluate_live_order_kill_switch" not in source
    assert "resolve_runtime_mode" not in source
    assert "build_platform_status" not in source
    assert "submit_order" not in source
    assert "cancel_order" not in source
    assert "oanda_adapter" not in source
