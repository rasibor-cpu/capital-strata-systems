"""Reporting-consistency remediation: credential presence vs auth/connection/authority."""

from __future__ import annotations

from backend.runtime.broker_readiness_framework import compute_broker_readiness_score
from backend.runtime.canonical_account_snapshot import PROVENANCE_VALUES
from backend.runtime.canonical_broker_runtime_state import STATUS_FAIL, STATUS_NOT_TESTED, STATUS_PASS
from backend.runtime.canonical_broker_state_adapter import (
    adapt_canonical_state_to_legacy_broker_payload,
    map_canonical_credential_status_to_reporting,
    project_broker_reporting_fields,
)
from backend.runtime.canonical_broker_state_builder import build_canonical_broker_runtime_state
from backend.runtime.startup_summary import build_live_startup_summary
from dashboard.runtime.frontend_contract import build_frontend_payload


def _paper_payload(*, credentials_present: bool = True, **overrides):
    diagnostics = {
        "broker": "coinbase",
        "broker_name": "COINBASE",
        "credentials_present": credentials_present,
        "credential_status": "PRESENT" if credentials_present else "MISSING",
        "key_present": credentials_present,
        "private_key_present": credentials_present,
        "pem_valid": credentials_present,
        "failure_reason": "NONE" if credentials_present else "MISSING_CREDENTIALS",
        "readiness_status": "READY" if credentials_present else "BLOCKED",
        "recommended_action": (
            "No credential remediation required"
            if credentials_present
            else "Configure COINBASE read-only credentials"
        ),
        "authentication_attempted": False,
        "authenticated": False,
    }
    payload = {
        "selected_broker": "COINBASE",
        "broker": "COINBASE",
        "broker_mode": "paper",
        "mode": "paper",
        "credential_status": "PRESENT" if credentials_present else "MISSING",
        "credentials_present": credentials_present,
        "broker_credential_diagnostics": diagnostics,
        "credential_diagnostics": diagnostics,
        "broker_connected": False,
        "broker_authenticated": False,
        "authentication_status": "NOT_TESTED",
        "connection_status": "NOT_TESTED",
        "market_data_status": "NOT_TESTED",
        "operator_requested_live": False,
        "execution_scope": "PAPER_OR_NOT_SELECTED",
        "broker_execution_enabled": False,
        "execution_allowed": False,
        "live_authority_state": "BLOCKED",
        "authority_reason": "Operator Intent Missing",
        "broker_guard": "REJECT_BEFORE_BROKER",
        "live_micro_pilot_state": "DISARMED",
        "connection_error": "",
    }
    payload.update(overrides)
    return payload


def _surfaces(payload: dict):
    from backend.runtime.live_readiness_state_machine import evaluate_live_readiness_state

    canonical = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode=str(payload.get("broker_mode") or payload.get("mode") or "paper"),
        runtime_payload=payload,
        env=payload.get("env") if isinstance(payload.get("env"), dict) else None,
    )
    summary = build_live_startup_summary(payload)
    live_state = evaluate_live_readiness_state(payload).readiness_state
    reporting = project_broker_reporting_fields(
        {
            **payload,
            "canonical_broker_runtime_state": canonical.to_dict(),
            "readiness_state": live_state,
        },
        credential_diagnostics=payload.get("broker_credential_diagnostics"),
    )
    frontend = build_frontend_payload(
        {
            "broker_summary": {
                **payload,
                "canonical_broker_runtime_state": {
                    **canonical.to_dict(),
                    "readiness_score": reporting["readiness_score"],
                    "failure_reason": reporting["failure_reason"],
                },
                "readiness_state": live_state,
                "recommended_action": reporting["recommended_action"],
            }
        }
    )
    broker = frontend["sections"]["broker"]
    launcher = {
        "credentials_present": reporting["credentials_present"],
        "credential_status": reporting["credential_status"],
        "authentication_status": reporting["authentication_status"],
        "connection_status": reporting["connection_status"],
        "market_data_status": reporting["market_data_status"],
        "operator_requested_live": reporting["operator_requested_live"],
        "execution_allowed": reporting["execution_allowed"],
        "live_authority_state": reporting["live_authority_state"],
        "authority_reason": reporting["authority_reason"],
        "execution_scope": reporting["execution_scope"],
        "failure_reason": reporting["failure_reason"],
        "readiness_score": reporting["readiness_score"],
        "readiness_state": reporting["readiness_state"],
        "recommended_action": reporting["recommended_action"],
        "status_provenance": reporting["status_provenance"],
    }
    return canonical, summary, reporting, broker, launcher


def test_reporting_consistency_paper_mode_credentials_present_not_contaminated() -> None:
    payload = _paper_payload(
        connection_error="ENVIRONMENT_CONTAMINATION",
        failure_reason="ENVIRONMENT_CONTAMINATION",
        canonical_broker_environment={
            "profile": "PAPER",
            "environment": "paper",
            "contamination_keys": ["COINBASE_CDP_KEY_NAME", "COINBASE_CDP_PRIVATE_KEY_PATH"],
            "validation_status": "FAIL",
            "failure_reasons": ["live_credential_in_paper_profile"],
            "status": "FAIL",
        },
    )
    canonical, summary, reporting, broker, launcher = _surfaces(payload)
    diagnostics = summary["startup_diagnostics"]
    # Phase 154A pre-existing composite: credentials_present + not execution_enabled = 2/6.
    expected_score = compute_broker_readiness_score(
        credentials_present=True,
        authenticated=False,
        connected=False,
        account_loaded=False,
        market_data_ready=False,
        execution_enabled=False,
    )

    assert canonical.credential_status == STATUS_PASS
    assert reporting["credentials_present"] is True
    assert reporting["credential_status"] == "PRESENT"
    assert canonical.authentication_status == "NOT_TESTED"
    assert canonical.connection_status == "NOT_TESTED"
    assert canonical.market_data_status == "NOT_TESTED"
    assert reporting["operator_requested_live"] is False
    assert canonical.execution_allowed is False
    assert reporting["live_authority_state"] == "BLOCKED"
    assert "Operator Intent Missing" in str(reporting["authority_reason"])
    assert reporting["execution_scope"] == "PAPER_OR_NOT_SELECTED"
    assert canonical.overall_status in {"RED", "FAIL_CLOSED"}
    assert reporting["failure_reason"] != "ENVIRONMENT_CONTAMINATION"
    assert reporting["contamination_keys"] == []
    assert reporting["environment_validation_status"] == "PASS"
    assert "configure" not in reporting["recommended_action"].lower()
    assert canonical.status_provenance.get("credentials") == "UNKNOWN"
    assert canonical.status_provenance.get("credentials") in PROVENANCE_VALUES
    assert canonical.status_provenance.get("credentials") != "SIMULATION"
    assert diagnostics["readiness_score"] == canonical.readiness_score == reporting["readiness_score"] == broker["readiness_score"] == launcher["readiness_score"]
    assert diagnostics["readiness_score"] == expected_score == 33.33
    # Operational readiness remains unvalidated for live broker checks.
    assert diagnostics["readiness_state"] == "CLIENT_CREATED"
    assert summary["Readiness State"] == "CLIENT_CREATED"
    assert summary["Authentication"] == "NOT_TESTED"
    assert summary["Connection"] == "NOT_TESTED"


def test_reporting_consistency_paper_mode_credentials_absent() -> None:
    payload = _paper_payload(credentials_present=False)
    canonical, summary, reporting, broker, launcher = _surfaces(payload)

    assert canonical.credential_status == STATUS_FAIL
    assert reporting["credentials_present"] is False
    assert reporting["credential_status"] == "MISSING"
    assert canonical.authentication_status == "NOT_TESTED"
    assert canonical.connection_status == "NOT_TESTED"
    assert canonical.execution_allowed is False
    assert reporting["operator_requested_live"] is False
    assert "configure" in reporting["recommended_action"].lower()
    assert broker["credentials_present"] is False
    assert launcher["execution_allowed"] is False


def test_reporting_consistency_live_auth_failure_preserves_credential_presence() -> None:
    payload = _paper_payload(
        broker_mode="live",
        mode="live",
        operator_requested_live=True,
        execution_scope="LIVE READ-ONLY VALIDATION",
        authentication_attempted=True,
        authentication_status="FAIL",
        broker_authenticated=False,
        connected=False,
        connection_status="FAIL",
        authority_reason="Authentication Not Verified",
        broker_credential_diagnostics={
            "broker": "coinbase",
            "credentials_present": True,
            "credential_status": "PRESENT",
            "failure_reason": "AUTH_FAILED",
            "recommended_action": "Verify broker credentials and read-only permissions",
            "authentication_attempted": True,
            "authenticated": False,
            "readiness_status": "READY",
        },
    )
    payload["broker_credential_diagnostics"]["credentials_present"] = True
    canonical, summary, reporting, broker, launcher = _surfaces(payload)

    assert canonical.credential_status == STATUS_PASS
    assert reporting["credentials_present"] is True
    assert reporting["credential_status"] == "PRESENT"
    assert canonical.authentication_status == STATUS_FAIL
    assert reporting["credentials_present"] is True
    assert "missing" not in reporting["credential_status"].lower()
    assert canonical.execution_allowed is False
    assert broker["execution_allowed"] is False
    assert launcher["execution_allowed"] is False


def test_reporting_consistency_environment_contamination_requires_evidence() -> None:
    clean = _paper_payload(
        failure_reason="ENVIRONMENT_CONTAMINATION",
        connection_error="ENVIRONMENT_CONTAMINATION",
    )
    dirty = _paper_payload(
        broker_mode="live",
        mode="live",
        operator_requested_live=True,
        env={"COINBASE_TEST_ORDER_USD": "1.00", "COINBASE_CDP_KEY_NAME": "present"},
        environment_diagnostics={
            "status": "FAIL",
            "contamination_keys": ["COINBASE_TEST_ORDER_USD"],
        },
    )
    clean_state = build_canonical_broker_runtime_state(broker="COINBASE", mode="paper", runtime_payload=clean)
    dirty_state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload=dirty,
        env=dirty["env"],
    )

    assert clean_state.failure_reason != "ENVIRONMENT_CONTAMINATION"
    assert clean_state.environment_evidence.get("status") == "PASS"
    assert dirty_state.failure_reason == "ENVIRONMENT_CONTAMINATION"
    assert dirty_state.environment_evidence.get("status") == "FAIL"
    assert "COINBASE_TEST_ORDER_USD" in dirty_state.environment_evidence.get("contamination_keys", [])


def test_reporting_consistency_cross_surface_parity() -> None:
    payload = _paper_payload()
    canonical, summary, reporting, broker, launcher = _surfaces(payload)
    diagnostics = summary["startup_diagnostics"]

    assert diagnostics["credentials_present"] is True
    assert diagnostics["credential_status"] == reporting["credential_status"] == launcher["credential_status"]
    assert broker["credential_status"] in {"PRESENT", "PASS"}
    assert map_canonical_credential_status_to_reporting(canonical.credential_status) == "PRESENT"
    assert diagnostics["authentication_status"] == canonical.authentication_status == reporting["authentication_status"]
    assert diagnostics["connection_status"] == canonical.connection_status == reporting["connection_status"]
    assert diagnostics["operator_requested_live"] is False
    assert diagnostics["execution_enabled"] is False
    assert canonical.execution_allowed is False
    assert broker["execution_allowed"] is False
    assert launcher["execution_allowed"] is False
    assert diagnostics["readiness_score"] == reporting["readiness_score"] == broker["readiness_score"] == launcher["readiness_score"]
    assert diagnostics["failure_reason"] == reporting["failure_reason"]
    assert "configure" not in diagnostics["recommended_action"].lower()


def test_reporting_consistency_safety_regression_paper_blocks_execution() -> None:
    payload = _paper_payload(operator_requested_live=False, broker_execution_enabled=False)
    canonical, summary, reporting, broker, launcher = _surfaces(payload)

    assert reporting["operator_requested_live"] is False
    assert canonical.execution_allowed is False
    assert canonical.live_trading_blocked is True
    assert canonical.broker_execution_armed is False
    assert summary["execution_allowed"] is False
    assert broker["execution_allowed"] is False
    assert launcher["execution_allowed"] is False
    assert reporting["live_authority_state"] == "BLOCKED"


def test_credential_status_mapping_pass_present_fail_missing_not_tested_preserved() -> None:
    assert map_canonical_credential_status_to_reporting(STATUS_PASS) == "PRESENT"
    assert map_canonical_credential_status_to_reporting("PASS") == "PRESENT"
    # FAIL without diagnostic evidence defaults to MISSING (absent/incomplete material).
    assert map_canonical_credential_status_to_reporting(STATUS_FAIL) == "MISSING"
    assert map_canonical_credential_status_to_reporting("FAIL") == "MISSING"
    assert map_canonical_credential_status_to_reporting(STATUS_NOT_TESTED) == "NOT_TESTED"
    assert map_canonical_credential_status_to_reporting("NOT_TESTED") == "NOT_TESTED"

    present_state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="paper",
        runtime_payload=_paper_payload(credentials_present=True),
    )
    missing_payload = _paper_payload(credentials_present=False)
    missing_state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="paper",
        runtime_payload=missing_payload,
    )
    present_legacy = adapt_canonical_state_to_legacy_broker_payload(
        present_state,
        base_payload={"broker_credential_diagnostics": _paper_payload(credentials_present=True)["broker_credential_diagnostics"]},
    )
    missing_legacy = adapt_canonical_state_to_legacy_broker_payload(
        missing_state,
        base_payload={"broker_credential_diagnostics": missing_payload["broker_credential_diagnostics"]},
    )

    assert present_state.credential_status == STATUS_PASS
    assert present_legacy["credential_status"] == "PRESENT"
    assert missing_state.credential_status == STATUS_FAIL
    assert missing_legacy["credential_status"] == "MISSING"


def test_credential_fail_absent_maps_missing_invalid_pem_maps_invalid() -> None:
    """Canonical FAIL covers both absence and present-but-invalid material."""
    from backend.runtime.broker_credential_diagnostics import diagnose_broker_credentials

    absent = diagnose_broker_credentials("coinbase", env={}).as_dict()
    invalid = diagnose_broker_credentials(
        "coinbase",
        env={
            "COINBASE_CDP_KEY_NAME": "organizations/example/apiKeys/example",
            "COINBASE_CDP_PRIVATE_KEY_PATH": "C:/does/not/exist-coinbase.pem",
        },
    ).as_dict()
    auth_failed_present = diagnose_broker_credentials(
        "coinbase",
        env={
            "COINBASE_CDP_KEY_NAME": "organizations/example/apiKeys/example",
            "COINBASE_CDP_PRIVATE_KEY": "-----BEGIN EC PRIVATE KEY-----\nMQw=\n-----END EC PRIVATE KEY-----",
        },
        authentication_attempted=True,
        authenticated=False,
    ).as_dict()

    assert absent["credentials_present"] is False
    assert absent["failure_reason"] == "KEY_MISSING"
    assert map_canonical_credential_status_to_reporting(STATUS_FAIL, diagnostics=absent) == "MISSING"

    assert invalid["credentials_present"] is False
    assert invalid["key_present"] is True
    assert invalid["private_key_present"] is True
    assert invalid["pem_valid"] is False
    assert invalid["failure_reason"] == "PEM_INVALID"
    assert map_canonical_credential_status_to_reporting(STATUS_FAIL, diagnostics=invalid) == "INVALID"

    # Present-but-invalid still produces canonical FAIL (credentials_present=False), never PASS.
    invalid_state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="paper",
        runtime_payload={
            "selected_broker": "COINBASE",
            "broker_mode": "paper",
            "broker_credential_diagnostics": invalid,
            "credentials_present": False,
        },
    )
    assert invalid_state.credential_status == STATUS_FAIL
    invalid_legacy = adapt_canonical_state_to_legacy_broker_payload(
        invalid_state,
        base_payload={"broker_credential_diagnostics": invalid},
    )
    assert invalid_legacy["credential_status"] == "INVALID"
    assert invalid_legacy["credential_failure_reason"] == "PEM_INVALID"
    assert invalid_legacy["credentials_present"] is False

    # Auth failure with structurally valid credentials remains canonical PASS / PRESENT.
    assert auth_failed_present["credentials_present"] is True
    assert auth_failed_present["failure_reason"] == "AUTH_FAILED"
    auth_state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="live",
        runtime_payload={
            "selected_broker": "COINBASE",
            "broker_mode": "live",
            "broker_credential_diagnostics": auth_failed_present,
            "credentials_present": True,
            "authentication_attempted": True,
            "broker_authenticated": False,
            "operator_requested_live": True,
        },
    )
    assert auth_state.credential_status == STATUS_PASS
    assert map_canonical_credential_status_to_reporting(auth_state.credential_status, diagnostics=auth_failed_present) == "PRESENT"


def test_credential_provenance_uses_accepted_unknown_not_simulation() -> None:
    state = build_canonical_broker_runtime_state(
        broker="COINBASE",
        mode="paper",
        runtime_payload=_paper_payload(credentials_present=True),
    )
    assert state.status_provenance["credentials"] in PROVENANCE_VALUES
    assert state.status_provenance["credentials"] == "UNKNOWN"
    assert state.status_provenance["credentials"] != "SIMULATION"
    assert "LOCAL_VALIDATION" not in PROVENANCE_VALUES
    assert "SECRET_STORE" not in PROVENANCE_VALUES
    assert "CREDENTIAL_DIAGNOSTIC" not in PROVENANCE_VALUES


def test_readiness_state_exact_enums_across_surfaces() -> None:
    payload = _paper_payload()
    canonical, summary, reporting, broker, launcher = _surfaces(payload)
    diagnostics = summary["startup_diagnostics"]

    assert summary["Readiness State"] == "CLIENT_CREATED"
    assert summary["readiness_state"] == "CLIENT_CREATED"
    assert diagnostics["readiness_state"] == "CLIENT_CREATED"
    # Canonical readiness_state may mirror overall_status when progression was not stamped.
    assert canonical.readiness_state in {"CLIENT_CREATED", "RED"}
    assert reporting["readiness_state"] == "CLIENT_CREATED"
    assert reporting.get("canonical_readiness_state") in {"CLIENT_CREATED", "RED"}
    assert summary["Readiness"] == canonical.readiness_state
    assert summary["Overall Status"] == "RED"
    assert diagnostics["go_no_go"] == "NO GO"
    assert launcher["execution_allowed"] is False
    assert broker["execution_allowed"] is False
    assert launcher["readiness_state"] == "CLIENT_CREATED"
