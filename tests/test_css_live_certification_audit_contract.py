from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_certification_audit_is_read_only_and_uses_canonical_endpoints():
    text = (ROOT / "scripts" / "audit_css_live_certification.ps1").read_text(
        encoding="utf-8"
    )
    assert '"/mission-control/api/state"' in text
    assert '"/mission-control/api/final-certification"' in text
    assert '"/mission-control/api/health"' in text
    assert '"/mission-control/api/runtime"' in text
    assert "Invoke-RestMethod" in text
    assert "-Method Get" in text
    assert "POST" not in text
    assert "execution_allowed" in text
    assert "live_trading_blocked" in text
    assert "broker_execution_armed" in text


def test_live_certification_audit_avoids_powershell7_ternary_syntax():
    text = (ROOT / "scripts" / "audit_css_live_certification.ps1").read_text(
        encoding="utf-8"
    )
    assert " ? " not in text
    assert "? $" not in text
    assert "[string]::IsNullOrWhiteSpace" in text


def test_live_certification_audit_fails_contradictory_certified_state_closed():
    text = (ROOT / "scripts" / "audit_css_live_certification.ps1").read_text(
        encoding="utf-8"
    )
    assert "Certification response is internally inconsistent" in text
    assert "certified_with_runtime_" in text
    assert "certified_with_production_readiness_" in text
    assert "certified_with_broker_evidence_missing" in text
    assert "certified_with_runtime_evidence_missing" in text
    assert "certified_with_incomplete_evidence" in text
    assert "certified_without_deployment_authorization" in text
    assert "exit 2" in text


def test_live_certification_audit_surfaces_runtime_root_cause_fields():
    text = (ROOT / "scripts" / "audit_css_live_certification.ps1").read_text(
        encoding="utf-8"
    )
    for token in (
        "source_status",
        "source_freshness",
        "source_confidence",
        "runtime_health",
        "supervisor_state",
        "broker_health",
        "broker_failure_reason",
        "rc1_certification",
        "rc1_operational",
        "runtime_readiness",
        "broker_readiness",
        "runtime blockers",
    ):
        assert token in text


def test_live_certification_audit_surfaces_broker_stage_diagnostics_and_blocker_names():
    text = (ROOT / "scripts" / "audit_css_live_certification.ps1").read_text(
        encoding="utf-8"
    )
    for token in (
        "broker_authentication",
        "broker_account",
        "broker_market_data",
        "broker warnings",
        "$deploymentBlockers",
    ):
        assert token in text


def test_live_certification_audit_reports_missing_credential_field_names_only():
    text = (ROOT / "scripts" / "audit_css_live_certification.ps1").read_text(
        encoding="utf-8"
    )
    assert "credential_status" in text
    assert "credential_reason" in text
    assert "missing credential fields" in text
    assert "credential_action" in text
