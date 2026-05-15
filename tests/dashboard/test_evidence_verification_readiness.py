from __future__ import annotations

import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_evidence_verification_readiness_payload,
)
from dashboard.runtime.evidence_notarization_readiness import (
    build_evidence_notarization_readiness_payload,
)
from dashboard.runtime.evidence_signature_readiness import (
    build_evidence_signature_readiness_payload,
)
from dashboard.runtime.evidence_verification_readiness import (
    EVIDENCE_VERIFICATION_READINESS_VERSION,
    VERIFICATION_STATUS_BLOCKED,
    VERIFICATION_STATUS_NOT_VERIFIED,
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


def _signature_readiness_payload():
    return build_evidence_signature_readiness_payload(
        _manifest_hash_payload(),
        generated_at_utc="2026-05-15T00:03:00+00:00",
    )


def _notarization_readiness_payload():
    return build_evidence_notarization_readiness_payload(
        _signature_readiness_payload(),
        generated_at_utc="2026-05-15T00:04:00+00:00",
    )


def test_verification_readiness_is_not_verified_and_review_only() -> None:
    readiness = build_evidence_verification_readiness_payload(
        _manifest_hash_payload(),
        signature_readiness_payload=_signature_readiness_payload(),
        notarization_readiness_payload=_notarization_readiness_payload(),
        generated_at_utc="2026-05-15T00:05:00+00:00",
    )

    assert readiness["payload_version"] == EVIDENCE_VERIFICATION_READINESS_VERSION
    assert readiness["verification_readiness_id"].startswith("VERIFYREADY-")
    assert readiness["verification_status"] == VERIFICATION_STATUS_NOT_VERIFIED
    assert readiness["verification_performed"] is False
    assert readiness["archive_read_performed"] is False
    assert readiness["external_file_read_performed"] is False
    assert readiness["signature_verified"] is False
    assert readiness["notarization_verified"] is False
    assert readiness["hash_recheck_available"] is True
    assert readiness["manual_verification_review_required"] is True
    assert readiness["blockers"] == []


def test_verification_readiness_blocks_missing_manifest_hash() -> None:
    readiness = build_evidence_verification_readiness_payload({})

    assert readiness["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert readiness["hash_recheck_available"] is False
    assert "MANIFEST_HASH_ID_MISSING" in readiness["blockers"]
    assert "COMBINED_MANIFEST_HASH_MISSING" in readiness["blockers"]
    assert "HASH_RECHECK_UNAVAILABLE" in readiness["warnings"]
    assert "VERIFICATION_READINESS_BLOCKERS_PRESENT" in readiness["warnings"]


def test_verification_readiness_blocks_unsafe_inputs_without_performing_them() -> None:
    readiness = build_evidence_verification_readiness_payload(
        {
            **_manifest_hash_payload(),
            "archive_write_performed": True,
            "trading_armed": True,
        },
        signature_readiness_payload={
            **_signature_readiness_payload(),
            "signing_status": "SIGNED",
            "signature_generated": True,
            "execution_allowed": True,
        },
        notarization_readiness_payload={
            **_notarization_readiness_payload(),
            "notarization_status": "NOTARIZED",
            "broker_mutation_allowed": True,
            "persistence_enabled": True,
        },
        verification_performed=True,
        archive_read_performed=True,
        external_file_read_performed=True,
        signature_verified=True,
        notarization_verified=True,
    )

    assert readiness["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert "SIGNATURE_STATUS_UNEXPECTED" in readiness["blockers"]
    assert "NOTARIZATION_STATUS_UNEXPECTED" in readiness["blockers"]
    assert "SIGNATURE_GENERATED_UNEXPECTED" in readiness["blockers"]
    assert "VERIFICATION_PERFORMED_UNEXPECTED" in readiness["blockers"]
    assert "ARCHIVE_READ_PERFORMED_UNEXPECTED" in readiness["blockers"]
    assert "EXTERNAL_FILE_READ_PERFORMED_UNEXPECTED" in readiness["blockers"]
    assert "SIGNATURE_VERIFIED_UNEXPECTED" in readiness["blockers"]
    assert "NOTARIZATION_VERIFIED_UNEXPECTED" in readiness["blockers"]
    assert "ARCHIVE_WRITE_PERFORMED_UNEXPECTED" in readiness["blockers"]
    assert "TRADING_ARMED_UNEXPECTED" in readiness["blockers"]
    assert "EXECUTION_ALLOWED_UNEXPECTED" in readiness["blockers"]
    assert "BROKER_MUTATION_ALLOWED_UNEXPECTED" in readiness["blockers"]
    assert "PERSISTENCE_ENABLED_UNEXPECTED" in readiness["blockers"]
    assert readiness["verification_performed"] is False
    assert readiness["archive_read_performed"] is False
    assert readiness["external_file_read_performed"] is False
    assert readiness["signature_verified"] is False
    assert readiness["notarization_verified"] is False


def test_verification_readiness_redacts_sensitive_payload_fields() -> None:
    readiness = build_evidence_verification_readiness_payload(
        {
            **_manifest_hash_payload(),
            "api_secret": "do-not-export",
        },
        signature_readiness_payload={
            **_signature_readiness_payload(),
            "private_key": "private key do-not-export",
        },
        notarization_readiness_payload=_notarization_readiness_payload(),
    )
    encoded = json.dumps(readiness)

    assert "do-not-export" not in encoded
    assert readiness["hash_recheck_available"] is True


def test_verification_readiness_safety_flags_are_closed() -> None:
    readiness = build_evidence_verification_readiness_payload(
        _manifest_hash_payload(),
        signature_readiness_payload=_signature_readiness_payload(),
        notarization_readiness_payload=_notarization_readiness_payload(),
    )

    assert readiness["trading_armed"] is False
    assert readiness["execution_allowed"] is False
    assert readiness["broker_mutation_allowed"] is False
    assert readiness["persistence_enabled"] is False
    assert readiness["audit_payload"]["no_external_archive_read"] is True
    assert readiness["audit_payload"]["no_external_file_read"] is True
    assert readiness["audit_payload"]["no_verification_performed"] is True
    assert readiness["audit_payload"]["no_signature_verification"] is True
    assert readiness["audit_payload"]["no_notarization_verification"] is True
    assert readiness["audit_payload"]["no_broker_calls"] is True
    assert readiness["audit_payload"]["no_order_placement"] is True


def test_verification_readiness_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}
    route = routes["/api/v1/evidence-verification-readiness"]
    payload = get_evidence_verification_readiness_payload()

    assert "GET" in getattr(route, "methods", set())
    assert "POST" not in getattr(route, "methods", set())
    assert payload["verification_status"] == VERIFICATION_STATUS_NOT_VERIFIED
    assert payload["manual_verification_review_required"] is True
    assert payload["verification_performed"] is False
    assert payload["archive_read_performed"] is False
    assert payload["external_file_read_performed"] is False
    assert payload["hash_recheck_available"] is True
    assert payload["source_metadata"]["no_external_archive_read"] is True
    assert payload["source_metadata"]["no_verification_performed"] is True


def test_verification_readiness_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "Evidence Verification Readiness" in markup
    assert "No external archive file is read and no verification is performed" in markup
    assert "/api/v1/evidence-verification-readiness" in markup


def test_verification_readiness_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_evidence_verification_readiness_payload(
        _manifest_hash_payload(),
        signature_readiness_payload=_signature_readiness_payload(),
        notarization_readiness_payload=_notarization_readiness_payload(),
    )

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["broker_mutation_allowed"] is False
