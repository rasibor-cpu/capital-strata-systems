from __future__ import annotations

import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_post_pilot_reconciliation_payload,
)
from dashboard.runtime.post_pilot_reconciliation_workflow import (
    POST_PILOT_RECONCILIATION_PAYLOAD_VERSION,
    RECONCILIATION_INCOMPLETE,
    RECONCILIATION_MATCH,
    RECONCILIATION_MISMATCH,
    RECONCILIATION_REVIEW_REQUIRED,
    build_post_pilot_reconciliation_payload,
    check_audit_evidence_presence,
    check_replay_evidence_presence,
    compare_balance_deltas,
    compare_order_counts,
    compare_position_state,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page
from dashboard.web.web_app import create_app as create_web_app


def _matching_payload(**overrides):
    base = {
        "broker_balance_before": {"total_equity": "100.00"},
        "broker_balance_after": {"total_equity": "99.75"},
        "css_balance_before": {"total_equity": "100.00"},
        "css_balance_after": {"total_equity": "99.75"},
        "expected_order_count": 1,
        "observed_order_count": 1,
        "expected_position_state": "FLAT_OR_CLOSED",
        "observed_position_state": "flat",
        "replay_correlation_ids": ["CORR-1"],
        "audit_action_ids": ["OPACT-1"],
        "evidence_hash_chain_id": "EVCHAIN-1",
        "generated_at_utc": "2026-05-15T00:00:00+00:00",
    }
    base.update(overrides)
    return build_post_pilot_reconciliation_payload(**base)


def test_post_pilot_reconciliation_match_state() -> None:
    payload = _matching_payload()

    assert payload["payload_version"] == POST_PILOT_RECONCILIATION_PAYLOAD_VERSION
    assert payload["reconciliation_id"].startswith("POSTREC-")
    assert payload["reconciliation_status"] == RECONCILIATION_MATCH
    assert payload["mismatch_flags"] == []
    assert payload["warnings"] == []
    assert payload["broker"] == "Coinbase Advanced"
    assert payload["symbol"] == "BTC-USD"
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False
    assert payload["audit_payload"]["no_order_placement"] is True


def test_post_pilot_reconciliation_review_required_for_missing_links() -> None:
    payload = _matching_payload(
        replay_correlation_ids=[],
        audit_action_ids=[],
    )

    assert payload["reconciliation_status"] == RECONCILIATION_REVIEW_REQUIRED
    assert "REPLAY_EVIDENCE_MISSING" in payload["warnings"]
    assert "AUDIT_ACTION_EVIDENCE_MISSING" in payload["warnings"]
    assert payload["mismatch_flags"] == []


def test_post_pilot_reconciliation_mismatch_flags() -> None:
    payload = _matching_payload(
        broker_balance_after={"total_equity": "99.60"},
        observed_order_count=0,
        observed_position_state="OPEN",
    )

    assert payload["reconciliation_status"] == RECONCILIATION_MISMATCH
    assert "BALANCE_DELTA_MISMATCH" in payload["mismatch_flags"]
    assert "ORDER_COUNT_MISMATCH" in payload["mismatch_flags"]
    assert "POSITION_STATE_MISMATCH" in payload["mismatch_flags"]


def test_post_pilot_reconciliation_incomplete_state() -> None:
    payload = build_post_pilot_reconciliation_payload(
        generated_at_utc="2026-05-15T00:00:00+00:00",
    )

    assert payload["reconciliation_status"] == RECONCILIATION_INCOMPLETE
    assert "BROKER_BALANCE_EVIDENCE_INCOMPLETE" in payload["mismatch_flags"]
    assert "CSS_BALANCE_EVIDENCE_INCOMPLETE" in payload["mismatch_flags"]
    assert "ORDER_COUNT_EVIDENCE_INCOMPLETE" in payload["mismatch_flags"]
    assert "POSITION_STATE_EVIDENCE_INCOMPLETE" in payload["mismatch_flags"]
    assert "REPLAY_EVIDENCE_MISSING" in payload["warnings"]
    assert "AUDIT_ACTION_EVIDENCE_MISSING" in payload["warnings"]


def test_post_pilot_comparison_helpers() -> None:
    assert compare_balance_deltas(
        broker_balance_before=100,
        broker_balance_after=99.5,
        css_balance_before=100,
        css_balance_after=99.5,
    ) == []
    assert compare_balance_deltas(
        broker_balance_before=100,
        broker_balance_after=99,
        css_balance_before=100,
        css_balance_after=99.5,
    ) == ["BALANCE_DELTA_MISMATCH"]
    assert compare_order_counts(expected_order_count=1, observed_order_count=1) == []
    assert compare_order_counts(expected_order_count=1, observed_order_count=2) == [
        "ORDER_COUNT_MISMATCH"
    ]
    assert compare_position_state(
        expected_position_state="FLAT_OR_CLOSED",
        observed_position_state="closed",
    ) == []
    assert compare_position_state(
        expected_position_state="FLAT_OR_CLOSED",
        observed_position_state="open",
    ) == ["POSITION_STATE_MISMATCH"]
    assert check_replay_evidence_presence(["CORR-1"]) == []
    assert check_audit_evidence_presence(["OPACT-1"]) == []


def test_post_pilot_reconciliation_redacts_sensitive_notes() -> None:
    payload = _matching_payload(notes="token=SHOULD_NOT_LEAK")
    encoded = json.dumps(payload, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert payload["notes"] == "REDACTED"
    assert payload["source_metadata"]["secrets_redacted"] is True


def test_post_pilot_reconciliation_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}
    route = routes["/api/v1/post-pilot-reconciliation"]
    payload = get_post_pilot_reconciliation_payload()

    assert "GET" in getattr(route, "methods", set())
    assert "POST" not in getattr(route, "methods", set())
    assert payload["reconciliation_status"] == RECONCILIATION_INCOMPLETE
    assert payload["evidence_hash_chain_id"].startswith("EVCHAIN-")
    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_placement"] is True
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False


def test_post_pilot_reconciliation_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "Post-Pilot Reconciliation" in markup
    assert "Reconciliation Evidence Links" in markup
    assert "Reconciliation does not authorize additional trading" in markup
    assert "/api/v1/post-pilot-reconciliation" in markup


def test_post_pilot_reconciliation_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_post_pilot_reconciliation_payload()

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["broker_mutation_allowed"] is False
