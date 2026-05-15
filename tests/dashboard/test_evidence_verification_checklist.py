from __future__ import annotations

import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_evidence_verification_checklist_payload,
)
from dashboard.runtime.evidence_notarization_readiness import (
    build_evidence_notarization_readiness_payload,
)
from dashboard.runtime.evidence_signature_readiness import (
    build_evidence_signature_readiness_payload,
)
from dashboard.runtime.evidence_verification_checklist import (
    CHECKLIST_STATUS_ELIGIBLE_FOR_MANUAL_REVIEW,
    CHECKLIST_STATUS_INCOMPLETE,
    CHECKLIST_STATUS_REVIEW_READY,
    EVIDENCE_VERIFICATION_CHECKLIST_VERSION,
    build_evidence_verification_checklist_payload,
)
from dashboard.runtime.evidence_verification_readiness import (
    build_evidence_verification_readiness_payload,
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


def _verification_readiness_payload():
    manifest = _manifest_hash_payload()
    signature = build_evidence_signature_readiness_payload(
        manifest,
        generated_at_utc="2026-05-15T00:03:00+00:00",
    )
    notarization = build_evidence_notarization_readiness_payload(
        signature,
        generated_at_utc="2026-05-15T00:04:00+00:00",
    )
    return build_evidence_verification_readiness_payload(
        manifest,
        signature_readiness_payload=signature,
        notarization_readiness_payload=notarization,
        generated_at_utc="2026-05-15T00:05:00+00:00",
    )


def test_verification_checklist_is_review_ready_and_export_only() -> None:
    checklist = build_evidence_verification_checklist_payload(
        _verification_readiness_payload(),
        generated_at_utc="2026-05-15T00:06:00+00:00",
    )

    assert checklist["payload_version"] == EVIDENCE_VERIFICATION_CHECKLIST_VERSION
    assert checklist["verification_checklist_id"].startswith("VERIFYCHECK-")
    assert checklist["checklist_status"] == CHECKLIST_STATUS_REVIEW_READY
    assert checklist["manual_verification_required"] is True
    assert checklist["manual_verification_recorded"] is False
    assert checklist["archive_read_performed"] is False
    assert checklist["external_file_read_performed"] is False
    assert checklist["verification_performed"] is False
    assert checklist["signature_verified"] is False
    assert checklist["notarization_verified"] is False
    assert checklist["blockers"] == []
    assert {item["item_id"] for item in checklist["missing_items"]} == {
        "manual_verification_recorded",
        "final_pcnrass_reference_captured",
    }


def test_verification_checklist_can_be_eligible_when_manual_references_are_supplied() -> None:
    checklist = build_evidence_verification_checklist_payload(
        _verification_readiness_payload(),
        manual_verification_recorded=True,
        final_pcnrass_reference_captured=True,
    )

    assert checklist["checklist_status"] == CHECKLIST_STATUS_ELIGIBLE_FOR_MANUAL_REVIEW
    assert checklist["missing_items"] == []
    assert checklist["blockers"] == []
    assert checklist["manual_verification_recorded"] is False


def test_verification_checklist_blocks_missing_readiness_evidence() -> None:
    checklist = build_evidence_verification_checklist_payload({})

    assert checklist["checklist_status"] == CHECKLIST_STATUS_INCOMPLETE
    assert "verification_readiness_present" in {
        item["item_id"] for item in checklist["missing_items"]
    }
    assert any(
        blocker.startswith("manifest_hash_copied:")
        for blocker in checklist["blockers"]
    )


def test_verification_checklist_blocks_unsafe_readiness_inputs_without_doing_them() -> None:
    checklist = build_evidence_verification_checklist_payload(
        {
            **_verification_readiness_payload(),
            "archive_read_performed": True,
            "external_file_read_performed": True,
            "verification_performed": True,
            "signature_verified": True,
            "notarization_verified": True,
            "trading_armed": True,
            "execution_allowed": True,
            "broker_mutation_allowed": True,
            "persistence_enabled": True,
        }
    )
    missing_ids = {item["item_id"] for item in checklist["missing_items"]}

    assert checklist["checklist_status"] == CHECKLIST_STATUS_INCOMPLETE
    assert "no_external_file_read_by_css" in missing_ids
    assert "no_archive_read_by_css" in missing_ids
    assert "no_verification_performed_by_css" in missing_ids
    assert "no_signature_verification_by_css" in missing_ids
    assert "no_notarization_verification_by_css" in missing_ids
    assert "trading_and_broker_safety_closed" in missing_ids
    assert checklist["archive_read_performed"] is False
    assert checklist["external_file_read_performed"] is False
    assert checklist["verification_performed"] is False
    assert checklist["signature_verified"] is False
    assert checklist["notarization_verified"] is False
    assert checklist["trading_armed"] is False
    assert checklist["execution_allowed"] is False
    assert checklist["broker_mutation_allowed"] is False
    assert checklist["persistence_enabled"] is False


def test_verification_checklist_redacts_sensitive_payload_fields() -> None:
    checklist = build_evidence_verification_checklist_payload(
        {
            **_verification_readiness_payload(),
            "api_secret": "do-not-export",
            "notes": "token=do-not-export",
        }
    )
    encoded = json.dumps(checklist)

    assert "do-not-export" not in encoded
    assert checklist["source_metadata"]["secrets_redacted"] is True


def test_verification_checklist_safety_flags_are_closed() -> None:
    checklist = build_evidence_verification_checklist_payload(
        _verification_readiness_payload()
    )

    assert checklist["trading_armed"] is False
    assert checklist["execution_allowed"] is False
    assert checklist["broker_mutation_allowed"] is False
    assert checklist["persistence_enabled"] is False
    assert checklist["audit_payload"]["no_external_archive_read"] is True
    assert checklist["audit_payload"]["no_external_file_read"] is True
    assert checklist["audit_payload"]["no_verification_performed"] is True
    assert checklist["audit_payload"]["no_signature_verification"] is True
    assert checklist["audit_payload"]["no_notarization_verification"] is True
    assert checklist["audit_payload"]["no_broker_calls"] is True
    assert checklist["audit_payload"]["no_order_placement"] is True


def test_verification_checklist_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}
    route = routes["/api/v1/evidence-verification-checklist"]
    payload = get_evidence_verification_checklist_payload()

    assert "GET" in getattr(route, "methods", set())
    assert "POST" not in getattr(route, "methods", set())
    assert payload["checklist_status"] == CHECKLIST_STATUS_REVIEW_READY
    assert payload["manual_verification_required"] is True
    assert payload["manual_verification_recorded"] is False
    assert payload["archive_read_performed"] is False
    assert payload["external_file_read_performed"] is False
    assert payload["verification_performed"] is False
    assert payload["source_metadata"]["no_external_file_read"] is True
    assert payload["source_metadata"]["no_verification_performed"] is True


def test_verification_checklist_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "Evidence Verification Checklist" in markup
    assert "Manual verification is not recorded and no archive file is read" in markup
    assert "Verification Checklist Missing Items" in markup
    assert "/api/v1/evidence-verification-checklist" in markup


def test_verification_checklist_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_evidence_verification_checklist_payload(
        _verification_readiness_payload()
    )

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["broker_mutation_allowed"] is False
