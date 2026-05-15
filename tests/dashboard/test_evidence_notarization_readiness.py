from __future__ import annotations

import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_evidence_notarization_readiness_payload,
)
from dashboard.runtime.evidence_notarization_readiness import (
    EVIDENCE_NOTARIZATION_READINESS_VERSION,
    NOTARIZATION_STATUS_BLOCKED,
    NOTARIZATION_STATUS_NOT_NOTARIZED,
    build_evidence_notarization_readiness_payload,
)
from dashboard.runtime.evidence_signature_readiness import (
    build_evidence_signature_readiness_payload,
)
from dashboard.runtime.post_pilot_archive_manifest_hash import (
    build_post_pilot_archive_manifest_hash_payload,
)
from dashboard.runtime.post_pilot_evidence_archive_export import (
    build_post_pilot_evidence_archive_export_payload,
)
from dashboard.runtime.post_pilot_reconciliation_workflow import (
    build_post_pilot_reconciliation_payload,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page
from dashboard.web.web_app import create_app as create_web_app


def _manifest_hash_payload():
    reconciliation = build_post_pilot_reconciliation_payload(
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
    archive = build_post_pilot_evidence_archive_export_payload(
        reconciliation=reconciliation,
        generated_at_utc="2026-05-15T00:01:00+00:00",
    )
    return build_post_pilot_archive_manifest_hash_payload(
        archive,
        generated_at_utc="2026-05-15T00:02:00+00:00",
    )


def _signature_readiness_payload():
    return build_evidence_signature_readiness_payload(
        _manifest_hash_payload(),
        generated_at_utc="2026-05-15T00:03:00+00:00",
    )


def test_notarization_readiness_is_not_notarized_and_review_only() -> None:
    readiness = build_evidence_notarization_readiness_payload(
        _signature_readiness_payload(),
        generated_at_utc="2026-05-15T00:04:00+00:00",
    )

    assert readiness["payload_version"] == EVIDENCE_NOTARIZATION_READINESS_VERSION
    assert readiness["notarization_readiness_id"].startswith("NOTARYREADY-")
    assert readiness["notarization_status"] == NOTARIZATION_STATUS_NOT_NOTARIZED
    assert readiness["external_notarization_required"] is False
    assert readiness["manual_notarization_review_required"] is True
    assert readiness["notarization_provider_selected"] is False
    assert readiness["notarization_provider_name"] == ""
    assert readiness["notarization_timestamp_present"] is False
    assert readiness["notarization_receipt_present"] is False
    assert readiness["notarization_file_written"] is False
    assert readiness["signing_key_present"] is False
    assert readiness["signing_key_exposed"] is False
    assert readiness["blockers"] == []


def test_notarization_readiness_blocks_missing_signature_evidence() -> None:
    readiness = build_evidence_notarization_readiness_payload({})

    assert readiness["notarization_status"] == NOTARIZATION_STATUS_BLOCKED
    assert "SIGNATURE_READINESS_ID_MISSING" in readiness["blockers"]
    assert "MANIFEST_HASH_ID_MISSING" in readiness["blockers"]
    assert "COMBINED_MANIFEST_HASH_MISSING" in readiness["blockers"]
    assert "NOTARIZATION_READINESS_BLOCKERS_PRESENT" in readiness["warnings"]


def test_notarization_readiness_blocks_unsafe_inputs_without_exposing_them() -> None:
    readiness = build_evidence_notarization_readiness_payload(
        {
            **_signature_readiness_payload(),
            "signature_generated": True,
            "external_notarization_performed": True,
            "archive_write_performed": True,
            "trading_armed": True,
        },
        notarization_provider_selected=True,
        notarization_provider_name="provider_token=do-not-export",
        notarization_timestamp_present=True,
        notarization_receipt_present=True,
        notarization_file_written=True,
        signing_key_present=True,
        signing_key_exposed=True,
    )
    encoded = json.dumps(readiness)

    assert readiness["notarization_status"] == NOTARIZATION_STATUS_BLOCKED
    assert "SIGNATURE_GENERATED_UNEXPECTED" in readiness["blockers"]
    assert "EXTERNAL_NOTARIZATION_PERFORMED_UNEXPECTED" in readiness["blockers"]
    assert "NOTARIZATION_PROVIDER_SELECTED_UNEXPECTED" in readiness["blockers"]
    assert "NOTARIZATION_TIMESTAMP_PRESENT_UNEXPECTED" in readiness["blockers"]
    assert "NOTARIZATION_RECEIPT_PRESENT_UNEXPECTED" in readiness["blockers"]
    assert "NOTARIZATION_FILE_WRITTEN_UNEXPECTED" in readiness["blockers"]
    assert "SIGNING_KEY_PRESENT_UNEXPECTED" in readiness["blockers"]
    assert "SIGNING_KEY_EXPOSED" in readiness["blockers"]
    assert "ARCHIVE_WRITE_PERFORMED_UNEXPECTED" in readiness["blockers"]
    assert "TRADING_ARMED_UNEXPECTED" in readiness["blockers"]
    assert readiness["notarization_provider_selected"] is False
    assert readiness["notarization_provider_name"] == ""
    assert readiness["notarization_receipt_present"] is False
    assert readiness["notarization_file_written"] is False
    assert readiness["signing_key_present"] is False
    assert readiness["signing_key_exposed"] is False
    assert "do-not-export" not in encoded


def test_notarization_readiness_safety_flags_are_closed() -> None:
    readiness = build_evidence_notarization_readiness_payload(
        _signature_readiness_payload()
    )

    assert readiness["trading_armed"] is False
    assert readiness["execution_allowed"] is False
    assert readiness["broker_mutation_allowed"] is False
    assert readiness["persistence_enabled"] is False
    assert readiness["archive_write_performed"] is False
    assert readiness["audit_payload"]["no_external_notarization"] is True
    assert readiness["audit_payload"]["no_notarization_provider_selected"] is True
    assert readiness["audit_payload"]["no_notarization_receipt"] is True
    assert readiness["audit_payload"]["no_notarization_file_write"] is True
    assert readiness["audit_payload"]["no_private_key_loaded"] is True
    assert readiness["audit_payload"]["no_broker_calls"] is True
    assert readiness["audit_payload"]["no_order_placement"] is True


def test_notarization_readiness_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}
    route = routes["/api/v1/evidence-notarization-readiness"]
    payload = get_evidence_notarization_readiness_payload()

    assert "GET" in getattr(route, "methods", set())
    assert "POST" not in getattr(route, "methods", set())
    assert payload["notarization_status"] == NOTARIZATION_STATUS_NOT_NOTARIZED
    assert payload["manual_notarization_review_required"] is True
    assert payload["notarization_provider_selected"] is False
    assert payload["notarization_receipt_present"] is False
    assert payload["notarization_file_written"] is False
    assert payload["source_metadata"]["no_external_notarization"] is True
    assert payload["source_metadata"]["no_notarization_file_write"] is True


def test_notarization_readiness_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "Notarization Readiness" in markup
    assert "No external notarization is performed and no notarization file is written" in markup
    assert "/api/v1/evidence-notarization-readiness" in markup


def test_notarization_readiness_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_evidence_notarization_readiness_payload(
        _signature_readiness_payload()
    )

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["broker_mutation_allowed"] is False
