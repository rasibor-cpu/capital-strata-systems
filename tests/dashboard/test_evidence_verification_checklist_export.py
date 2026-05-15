from __future__ import annotations

import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_evidence_verification_checklist_export_payload,
)
from dashboard.runtime.evidence_notarization_readiness import (
    build_evidence_notarization_readiness_payload,
)
from dashboard.runtime.evidence_signature_readiness import (
    build_evidence_signature_readiness_payload,
)
from dashboard.runtime.evidence_verification_checklist import (
    build_evidence_verification_checklist_payload,
)
from dashboard.runtime.evidence_verification_checklist_export import (
    EVIDENCE_VERIFICATION_CHECKLIST_EXPORT_VERSION,
    build_evidence_verification_checklist_export_payload,
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
from dashboard.web.web_app import _evidence_verification_checklist_print_page
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


def _verification_checklist_payload():
    manifest = _manifest_hash_payload()
    signature = build_evidence_signature_readiness_payload(
        manifest,
        generated_at_utc="2026-05-15T00:03:00+00:00",
    )
    notarization = build_evidence_notarization_readiness_payload(
        signature,
        generated_at_utc="2026-05-15T00:04:00+00:00",
    )
    readiness = build_evidence_verification_readiness_payload(
        manifest,
        signature_readiness_payload=signature,
        notarization_readiness_payload=notarization,
        generated_at_utc="2026-05-15T00:05:00+00:00",
    )
    return build_evidence_verification_checklist_payload(
        readiness,
        generated_at_utc="2026-05-15T00:06:00+00:00",
    )


def test_verification_checklist_export_is_print_safe_and_review_only() -> None:
    export = build_evidence_verification_checklist_export_payload(
        _verification_checklist_payload(),
        generated_at_utc="2026-05-15T00:07:00+00:00",
    )

    assert export["payload_version"] == EVIDENCE_VERIFICATION_CHECKLIST_EXPORT_VERSION
    assert export["verification_export_id"].startswith("VERIFYEXPORT-")
    assert export["verification_checklist_id"].startswith("VERIFYCHECK-")
    assert export["verification_readiness_id"].startswith("VERIFYREADY-")
    assert export["manual_verification_required"] is True
    assert export["manual_verification_recorded"] is False
    assert export["archive_read_performed"] is False
    assert export["external_file_read_performed"] is False
    assert export["verification_performed"] is False
    assert export["signature_verified"] is False
    assert export["notarization_verified"] is False
    assert export["required_items"]
    assert export["missing_items"]
    assert "No verification" in export["safety_disclaimer"]


def test_verification_checklist_export_preserves_missing_items_and_safety_flags() -> None:
    export = build_evidence_verification_checklist_export_payload(
        _verification_checklist_payload()
    )
    missing_ids = {item["item_id"] for item in export["missing_items"]}

    assert "manual_verification_recorded" in missing_ids
    assert "final_pcnrass_reference_captured" in missing_ids
    assert export["trading_armed"] is False
    assert export["execution_allowed"] is False
    assert export["broker_mutation_allowed"] is False
    assert export["persistence_enabled"] is False
    assert export["source_metadata"]["no_external_file_read"] is True
    assert export["source_metadata"]["no_verification_performed"] is True


def test_verification_checklist_export_sanitizes_sensitive_values() -> None:
    checklist = {
        **_verification_checklist_payload(),
        "warnings": ["token=do-not-export"],
        "required_items": [
            {
                "item_id": "secret_item",
                "label": "api_key=do-not-export",
                "completed": False,
                "required": True,
                "severity": "REVIEW",
                "message": "password=do-not-export",
            }
        ],
    }
    export = build_evidence_verification_checklist_export_payload(checklist)
    encoded = json.dumps(export)

    assert "do-not-export" not in encoded
    assert "REDACTED" in encoded
    assert export["source_metadata"]["secrets_redacted"] is True


def test_verification_checklist_export_forces_unsafe_source_flags_closed() -> None:
    export = build_evidence_verification_checklist_export_payload(
        {
            **_verification_checklist_payload(),
            "manual_verification_recorded": True,
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

    assert export["manual_verification_recorded"] is False
    assert export["archive_read_performed"] is False
    assert export["external_file_read_performed"] is False
    assert export["verification_performed"] is False
    assert export["signature_verified"] is False
    assert export["notarization_verified"] is False
    assert export["trading_armed"] is False
    assert export["execution_allowed"] is False
    assert export["broker_mutation_allowed"] is False
    assert export["persistence_enabled"] is False


def test_verification_checklist_export_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}
    route = routes["/api/v1/evidence-verification-checklist-export"]
    payload = get_evidence_verification_checklist_export_payload()

    assert "GET" in getattr(route, "methods", set())
    assert "POST" not in getattr(route, "methods", set())
    assert payload["manual_verification_recorded"] is False
    assert payload["archive_read_performed"] is False
    assert payload["external_file_read_performed"] is False
    assert payload["verification_performed"] is False
    assert payload["signature_verified"] is False
    assert payload["notarization_verified"] is False
    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_placement"] is True


def test_verification_checklist_print_view_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _evidence_verification_checklist_print_page()

    assert "/evidence-verification-checklist-print" in routes
    assert "Evidence Verification Checklist Print View" in markup
    assert "Print/export view only" in markup
    assert "No verification action" in markup
    assert "No verification was performed by CSS" in markup
    assert "/api/v1/evidence-verification-checklist-export" in markup


def test_verification_checklist_export_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_evidence_verification_checklist_export_payload(
        _verification_checklist_payload()
    )

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["broker_mutation_allowed"] is False
