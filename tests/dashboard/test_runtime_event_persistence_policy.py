from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_runtime_event_persistence_policy_inspection_payload,
)
from dashboard.runtime.runtime_event_persistence_policy import (
    DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY,
    RUNTIME_EVENT_PERSISTENCE_APPROVAL_VERSION,
    RUNTIME_EVENT_PERSISTENCE_POLICY_VERSION,
    RuntimeEventPersistencePolicy,
    get_runtime_event_persistence_policy_payload,
    validate_persistence_request,
)


def test_default_persistence_policy_is_disabled_and_read_only() -> None:
    payload = get_runtime_event_persistence_policy_payload()
    policy = payload["policy"]

    assert payload["payload_version"] == RUNTIME_EVENT_PERSISTENCE_POLICY_VERSION
    assert payload["read_only"] is True
    assert payload["mutation_endpoint_available"] is False
    assert payload["approval_grant_endpoint_available"] is False
    assert payload["persistence_activation_available"] is False
    assert payload["persistence_enabled"] is False
    assert policy["persistence_enabled"] is False
    assert policy["operator_approval_required"] is True
    assert policy["approval_token_required"] is True
    assert policy["redaction_required"] is True
    assert policy["audit_logging_required"] is True
    assert policy["allowed_export_formats"] == ["json"]


def test_default_policy_blocks_even_otherwise_complete_request() -> None:
    result = validate_persistence_request(
        requested_subsystems=["alerting"],
        requested_window_minutes=15,
        reason="controlled validation",
        operator_id="operator-1",
        approval_token="token-secret",
    )

    assert result["payload_version"] == RUNTIME_EVENT_PERSISTENCE_APPROVAL_VERSION
    assert result["status"] == "FAIL"
    assert "PERSISTENCE_DISABLED_BY_POLICY" in result["blocking_reasons"]
    assert result["persistence_activation_performed"] is False
    assert "VALIDATION_ONLY_NO_PERSISTENCE_ACTIVATION" in result["warnings"]


def test_approval_required_enforcement() -> None:
    policy = RuntimeEventPersistencePolicy(persistence_enabled=True)
    result = validate_persistence_request(
        requested_subsystems=["alerting"],
        requested_window_minutes=10,
        reason="operator missing",
        approval_token="token-secret",
        policy=policy,
    )

    assert result["status"] == "FAIL"
    assert "OPERATOR_APPROVAL_REQUIRED" in result["blocking_reasons"]


def test_missing_token_rejection() -> None:
    policy = RuntimeEventPersistencePolicy(persistence_enabled=True)
    result = validate_persistence_request(
        requested_subsystems=["alerting"],
        requested_window_minutes=10,
        reason="token missing",
        operator_id="operator-1",
        policy=policy,
    )

    assert result["status"] == "FAIL"
    assert "APPROVAL_TOKEN_REQUIRED" in result["blocking_reasons"]


def test_invalid_subsystem_rejection() -> None:
    policy = RuntimeEventPersistencePolicy(persistence_enabled=True)
    result = validate_persistence_request(
        requested_subsystems=["not_a_css_subsystem"],
        requested_window_minutes=10,
        reason="bad subsystem",
        operator_id="operator-1",
        approval_token="token-secret",
        policy=policy,
    )

    assert result["status"] == "FAIL"
    assert "UNAPPROVED_SUBSYSTEM:not_a_css_subsystem" in result["blocking_reasons"]


def test_invalid_window_rejection() -> None:
    policy = RuntimeEventPersistencePolicy(
        persistence_enabled=True,
        max_persistence_window_minutes=30,
    )
    zero = validate_persistence_request(
        requested_subsystems=["alerting"],
        requested_window_minutes=0,
        reason="zero window",
        operator_id="operator-1",
        approval_token="token-secret",
        policy=policy,
    )
    too_large = validate_persistence_request(
        requested_subsystems=["alerting"],
        requested_window_minutes=31,
        reason="too large",
        operator_id="operator-1",
        approval_token="token-secret",
        policy=policy,
    )

    assert "INVALID_PERSISTENCE_WINDOW" in zero["blocking_reasons"]
    assert "PERSISTENCE_WINDOW_EXCEEDS_POLICY" in too_large["blocking_reasons"]


def test_validation_can_pass_without_activating_persistence_under_custom_policy() -> None:
    policy = RuntimeEventPersistencePolicy(
        persistence_enabled=True,
        max_persistence_window_minutes=30,
        approved_subsystems=("alerting", "replay"),
    )
    result = validate_persistence_request(
        requested_subsystems=["alerting", "replay"],
        requested_window_minutes=30,
        reason="planning only",
        operator_id="operator-1",
        approval_token="token-secret",
        policy=policy,
        request_id="REQ-1",
    )

    assert result["status"] == "PASS"
    assert result["blocking_reasons"] == []
    assert result["request_id"] == "REQ-1"
    assert result["persistence_activation_performed"] is False
    assert result["audit_payload"]["persistence_activation_performed"] is False


def test_safe_inspection_api_output_and_route() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_runtime_event_persistence_policy_inspection_payload()

    assert "/api/v1/runtime-event-persistence-policy" in routes
    assert payload["read_only"] is True
    assert payload["persistence_enabled"] is False
    assert payload["policy"] == DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY.as_dict()


def test_approval_payload_is_redaction_safe() -> None:
    result = validate_persistence_request(
        requested_subsystems=["alerting"],
        requested_window_minutes=10,
        reason="contains token",
        operator_id="operator-1",
        approval_token="super-secret-token",
    )
    serialized = json.dumps(result, sort_keys=True)

    assert "super-secret-token" not in serialized
    assert result["audit_payload"]["approval_token"] == "REDACTED"
    assert result["audit_payload"]["approval_token_present"] is True
    assert result["audit_payload"]["secrets_redacted"] is True
