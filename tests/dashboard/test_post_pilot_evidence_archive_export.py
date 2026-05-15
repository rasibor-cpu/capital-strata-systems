from __future__ import annotations

import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_post_pilot_evidence_archive_export_payload,
)
from dashboard.runtime.post_pilot_evidence_archive_export import (
    POST_PILOT_ARCHIVE_EXPORT_PAYLOAD_VERSION,
    build_post_pilot_evidence_archive_export_payload,
)
from dashboard.runtime.post_pilot_reconciliation_workflow import (
    build_post_pilot_reconciliation_payload,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page
from dashboard.web.web_app import create_app as create_web_app


def _reconciliation_payload():
    return build_post_pilot_reconciliation_payload(
        broker_balance_before={"total_equity": "100.00"},
        broker_balance_after={"total_equity": "99.75"},
        css_balance_before={"total_equity": "100.00"},
        css_balance_after={"total_equity": "99.75"},
        expected_order_count=1,
        observed_order_count=1,
        observed_position_state="closed",
        replay_correlation_ids=["CORR-1"],
        audit_action_ids=["OPACT-1"],
        evidence_hash_chain_id="EVCHAIN-1",
        generated_at_utc="2026-05-15T00:00:00+00:00",
    )


def test_post_pilot_archive_export_package_creation() -> None:
    export = build_post_pilot_evidence_archive_export_payload(
        reconciliation=_reconciliation_payload(),
        incident_ids=["INC-1"],
        no_go_decision_ids=["NOGO-1"],
        fee_slippage_summary={"fees": "0.01", "slippage_pct": "0.02"},
        fill_summary={"fill_status": "FILLED", "filled_qty": "0.0001"},
        operator_conclusion="review complete",
        generated_at_utc="2026-05-15T00:01:00+00:00",
    )

    assert export["payload_version"] == POST_PILOT_ARCHIVE_EXPORT_PAYLOAD_VERSION
    assert export["archive_export_id"].startswith("POSTARCH-")
    assert export["reconciliation_id"].startswith("POSTREC-")
    assert export["reconciliation_status"] == "MATCH"
    assert export["evidence_hash_chain_id"] == "EVCHAIN-1"
    assert export["replay_correlation_ids"] == ["CORR-1"]
    assert export["audit_action_ids"] == ["OPACT-1"]
    assert export["incident_ids"] == ["INC-1"]
    assert export["no_go_decision_ids"] == ["NOGO-1"]
    assert export["operator_conclusion"] == "review complete"


def test_post_pilot_archive_export_safety_flags_are_closed() -> None:
    export = build_post_pilot_evidence_archive_export_payload(
        reconciliation=_reconciliation_payload(),
    )

    assert export["archive_write_performed"] is False
    assert export["trading_armed"] is False
    assert export["execution_allowed"] is False
    assert export["broker_mutation_allowed"] is False
    assert export["persistence_enabled"] is False
    assert export["audit_payload"]["approval_grant_endpoint_exists"] is False
    assert export["audit_payload"]["no_archive_file_write"] is True
    assert export["audit_payload"]["no_order_placement"] is True


def test_post_pilot_archive_export_default_summaries_are_review_safe() -> None:
    export = build_post_pilot_evidence_archive_export_payload(
        reconciliation=_reconciliation_payload(),
    )

    assert export["broker_balance_summary"]["before"] == {"total_equity": "100.00"}
    assert export["css_ledger_summary"]["after"] == {"total_equity": "99.75"}
    assert export["fee_slippage_summary"]["review_required"] is True
    assert export["fill_summary"]["review_required"] is True
    assert "does not write archive files" in export["safety_disclaimer"]


def test_post_pilot_archive_export_redacts_sensitive_values() -> None:
    export = build_post_pilot_evidence_archive_export_payload(
        reconciliation=_reconciliation_payload(),
        operator_conclusion="token=SHOULD_NOT_LEAK",
        broker_balance_summary={"api_key": "SHOULD_NOT_LEAK"},
    )
    encoded = json.dumps(export, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert export["operator_conclusion"] == "REDACTED"
    assert export["broker_balance_summary"]["api_key"] == "REDACTED"
    assert export["source_metadata"]["secrets_redacted"] is True


def test_post_pilot_archive_export_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}
    route = routes["/api/v1/post-pilot-evidence-archive-export"]
    payload = get_post_pilot_evidence_archive_export_payload()

    assert "GET" in getattr(route, "methods", set())
    assert "POST" not in getattr(route, "methods", set())
    assert payload["archive_export_id"].startswith("POSTARCH-")
    assert payload["archive_write_performed"] is False
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False
    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_disk_writes"] is True


def test_post_pilot_archive_export_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "Post-Pilot Evidence Archive Export" in markup
    assert "Archive Export Evidence Links" in markup
    assert "No archive file is written from this page" in markup
    assert "/api/v1/post-pilot-evidence-archive-export" in markup


def test_post_pilot_archive_export_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_post_pilot_evidence_archive_export_payload(
        reconciliation=_reconciliation_payload(),
    )

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["broker_mutation_allowed"] is False
