from __future__ import annotations

import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_post_pilot_archive_manifest_hash_payload,
)
from dashboard.runtime.post_pilot_archive_manifest_hash import (
    HASH_ALGORITHM,
    POST_PILOT_ARCHIVE_MANIFEST_HASH_VERSION,
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


def _archive_export(**overrides):
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
    base = {
        "reconciliation": reconciliation,
        "incident_ids": ["INC-1"],
        "no_go_decision_ids": ["NOGO-1"],
        "operator_conclusion": "review complete",
        "generated_at_utc": "2026-05-15T00:01:00+00:00",
    }
    base.update(overrides)
    return build_post_pilot_evidence_archive_export_payload(**base)


def test_archive_manifest_hash_is_deterministic_for_same_package() -> None:
    package = _archive_export()

    first = build_post_pilot_archive_manifest_hash_payload(
        package,
        generated_at_utc="2026-05-15T00:02:00+00:00",
    )
    second = build_post_pilot_archive_manifest_hash_payload(
        package,
        generated_at_utc="2026-05-15T00:03:00+00:00",
    )

    assert first["payload_version"] == POST_PILOT_ARCHIVE_MANIFEST_HASH_VERSION
    assert first["algorithm"] == HASH_ALGORITHM
    assert first["manifest_hash"] == second["manifest_hash"]
    assert first["combined_manifest_hash"] == second["combined_manifest_hash"]
    assert first["manifest_hash_id"] == second["manifest_hash_id"]
    assert first["manifest_hash_id"].startswith("POSTMAN-")
    assert first["archive_export_id"] == package["archive_export_id"]
    assert first["reconciliation_id"] == package["reconciliation_id"]
    assert first["evidence_hash_chain_id"] == "EVCHAIN-1"


def test_changed_archive_package_changes_manifest_hash() -> None:
    original = build_post_pilot_archive_manifest_hash_payload(_archive_export())
    changed = build_post_pilot_archive_manifest_hash_payload(
        _archive_export(operator_conclusion="different conclusion"),
    )

    assert original["manifest_hash"] != changed["manifest_hash"]
    assert original["manifest_hash_id"] != changed["manifest_hash_id"]


def test_archive_manifest_hash_redacts_sensitive_fields() -> None:
    package = _archive_export(
        broker_balance_summary={"api_key": "SHOULD_NOT_LEAK"},
        operator_conclusion="token=SHOULD_NOT_LEAK",
    )
    hashed = build_post_pilot_archive_manifest_hash_payload(package)
    encoded = json.dumps(hashed, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert hashed["redaction_required"] is True
    assert hashed["source_metadata"]["secrets_redacted"] is True


def test_archive_manifest_hash_safety_flags_are_closed() -> None:
    hashed = build_post_pilot_archive_manifest_hash_payload(_archive_export())

    assert hashed["archive_write_performed"] is False
    assert hashed["trading_armed"] is False
    assert hashed["execution_allowed"] is False
    assert hashed["broker_mutation_allowed"] is False
    assert hashed["persistence_enabled"] is False
    assert hashed["audit_payload"]["approval_grant_endpoint_exists"] is False
    assert hashed["audit_payload"]["no_archive_file_write"] is True
    assert hashed["audit_payload"]["no_order_placement"] is True


def test_archive_manifest_combined_hash_uses_ordered_evidence_references() -> None:
    hashed = build_post_pilot_archive_manifest_hash_payload(_archive_export())
    refs = hashed["audit_payload"]["evidence_references"]
    reference_types = {item["reference_type"] for item in refs}

    assert hashed["evidence_reference_count"] == len(refs)
    assert hashed["item_count"] > 0
    assert len(hashed["combined_manifest_hash"]) == 64
    assert "archive_export_id" in reference_types
    assert "reconciliation_id" in reference_types
    assert "evidence_hash_chain_id" in reference_types
    assert "replay_correlation_id" in reference_types
    assert "audit_action_id" in reference_types


def test_archive_manifest_hash_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}
    route = routes["/api/v1/post-pilot-archive-manifest-hash"]
    payload = get_post_pilot_archive_manifest_hash_payload()

    assert "GET" in getattr(route, "methods", set())
    assert "POST" not in getattr(route, "methods", set())
    assert payload["manifest_hash_id"].startswith("POSTMAN-")
    assert payload["algorithm"] == "sha256"
    assert payload["archive_write_performed"] is False
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False
    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_disk_writes"] is True


def test_archive_manifest_hash_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "Archive Manifest Hash" in markup
    assert "Archive manifest hashing is integrity evidence only" in markup
    assert "/api/v1/post-pilot-archive-manifest-hash" in markup


def test_archive_manifest_hash_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_post_pilot_archive_manifest_hash_payload(_archive_export())

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["broker_mutation_allowed"] is False
