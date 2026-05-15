from __future__ import annotations

import json

import pytest

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_operator_action_audit_ledger_payload,
)
from dashboard.runtime.operator_action_audit_ledger import (
    OPERATOR_ACTION_AUDIT_LEDGER_VERSION,
    SUPPORTED_OPERATOR_ACTION_TYPES,
    OperatorActionAuditLedger,
    build_operator_action_audit_ledger_payload,
    build_operator_action_audit_record,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page
from dashboard.web.web_app import create_app as create_web_app


def test_operator_action_audit_entry_creation_is_review_only() -> None:
    entry = build_operator_action_audit_record(
        action_type="READINESS_REVIEWED",
        operator_id="operator-1",
        source_page="/micro-live-pilot-readiness",
        source_api="/api/v1/micro-live-pilot-readiness",
        related_hash_chain_id="EVCHAIN-123",
        notes="readiness reviewed",
        generated_at_utc="2026-05-15T00:00:00+00:00",
    )

    assert entry["payload_version"] == OPERATOR_ACTION_AUDIT_LEDGER_VERSION
    assert entry["action_id"].startswith("OPACT-")
    assert entry["operator_id"] == "operator-1"
    assert entry["action_type"] == "READINESS_REVIEWED"
    assert entry["trading_armed"] is False
    assert entry["execution_allowed"] is False
    assert entry["broker_mutation_allowed"] is False
    assert entry["persistence_enabled"] is False
    assert entry["redaction_required"] is True
    assert entry["audit_payload"]["approval_grant_endpoint_exists"] is False
    assert entry["audit_payload"]["no_order_placement"] is True


def test_supported_action_types_are_declared_and_reject_unknown() -> None:
    assert "EVIDENCE_HASH_REVIEWED" in SUPPORTED_OPERATOR_ACTION_TYPES
    assert "PACKET_EXPORTED" in SUPPORTED_OPERATOR_ACTION_TYPES

    with pytest.raises(ValueError):
        build_operator_action_audit_record(action_type="APPROVE_TRADING")


def test_operator_action_audit_output_redacts_sensitive_notes() -> None:
    entry = build_operator_action_audit_record(
        action_type="INCIDENT_WORKSHEET_REVIEWED",
        notes="token=SHOULD_NOT_LEAK",
    )
    encoded = json.dumps(entry, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert entry["notes"] == "REDACTED"
    assert entry["audit_payload"]["secrets_redacted"] is True


def test_in_memory_ledger_records_and_filters_review_actions() -> None:
    ledger = OperatorActionAuditLedger()
    ledger.record_action(
        action_type="READINESS_REVIEWED",
        operator_id="operator-1",
        related_hash_chain_id="EVCHAIN-1",
        generated_at_utc="2026-05-15T00:00:00+00:00",
    )
    ledger.record_action(
        action_type="EVIDENCE_HASH_REVIEWED",
        operator_id="operator-2",
        related_hash_chain_id="EVCHAIN-2",
        generated_at_utc="2026-05-15T00:01:00+00:00",
    )

    payload = build_operator_action_audit_ledger_payload(
        ledger,
        action_type="EVIDENCE_HASH_REVIEWED",
    )

    assert len(ledger) == 2
    assert payload["entry_count"] == 1
    assert payload["entries"][0]["action_type"] == "EVIDENCE_HASH_REVIEWED"
    assert payload["sample_entry_count"] == 0
    assert payload["summary"]["counts_by_action_type"]["EVIDENCE_HASH_REVIEWED"] == 1
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False


def test_empty_ledger_returns_sample_entries_without_mutating() -> None:
    ledger = OperatorActionAuditLedger()
    payload = build_operator_action_audit_ledger_payload(
        ledger,
        related_hash_chain_id="EVCHAIN-SAMPLE",
        generated_at_utc="2026-05-15T00:00:00+00:00",
    )

    assert len(ledger) == 0
    assert payload["entry_count"] == 0
    assert payload["sample_entry_count"] == 2
    assert payload["sample_entries"][0]["sample_only"] is True
    assert payload["sample_entries"][0]["related_hash_chain_id"] == "EVCHAIN-SAMPLE"
    assert payload["writes_performed"] is False


def test_operator_action_audit_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}
    route = routes["/api/v1/operator-action-audit-ledger"]
    payload = get_operator_action_audit_ledger_payload()

    assert "GET" in getattr(route, "methods", set())
    assert "POST" not in getattr(route, "methods", set())
    assert payload["read_only"] is True
    assert payload["approval_grant_endpoint_exists"] is False
    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_placement"] is True
    assert payload["source_metadata"]["no_runtime_event_persistence"] is True


def test_operator_action_audit_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "Operator Action Audit" in markup
    assert "Audit Review Actions" in markup
    assert "Review actions do not approve or arm trading" in markup
    assert "/api/v1/operator-action-audit-ledger" in markup


def test_operator_action_audit_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_operator_action_audit_ledger_payload()

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["broker_mutation_allowed"] is False
