"""Phase 181 — production readiness and operational acceptance."""

from __future__ import annotations

from backend.certification import (
    AcceptanceStatus,
    CertificationEvidence,
    PRODUCTION_READINESS_REPORT_TITLES,
    ProductionReadinessCertificationEngine,
    build_production_readiness_report_suite,
)
from backend.certification.deployment_readiness import DEPLOYMENT_REQUIREMENTS
from backend.certification.disaster_recovery_readiness import (
    DISASTER_RECOVERY_REQUIREMENTS,
)
from backend.certification.endurance_readiness import ENDURANCE_REQUIREMENTS
from backend.certification.operational_acceptance import (
    OAT_REQUIREMENTS,
    evaluate_operational_acceptance,
)
from backend.certification.production_readiness_certification import (
    PLATFORM_REQUIREMENTS,
)
from backend.reports_center.producers import produce, registered_producer_codes
from backend.reports_center.registry import by_code
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS, resolve_section_slug


REPORT_CODES = {
    "production_readiness",
    "operational_acceptance",
    "endurance_readiness",
    "disaster_recovery_readiness",
    "deployment_readiness",
    "production_outstanding_blockers",
    "final_certification_summary",
}


def _evidence() -> list[CertificationEvidence]:
    requirements = sorted(
        {
            *PLATFORM_REQUIREMENTS,
            *OAT_REQUIREMENTS,
            *ENDURANCE_REQUIREMENTS,
            *DISASTER_RECOVERY_REQUIREMENTS,
            *DEPLOYMENT_REQUIREMENTS,
        }
    )
    return [
        CertificationEvidence(
            evidence_id=f"OAT-{index:03d}",
            area=requirement,
            status=AcceptanceStatus.PASS,
            reference=f"evidence://phase181/{requirement.lower()}",
            observed_at="2026-07-21T01:00:00+00:00",
            source="PHASE181_VERIFIED_FIXTURE",
            remediation=f"Re-capture {requirement.lower()} evidence if it expires.",
            verified=True,
        )
        for index, requirement in enumerate(requirements, start=1)
    ]


def _governance() -> dict:
    return {
        "governance_score": 100,
        "enterprise_risk_summary": {
            "risk_count": 3,
            "unmitigated_count": 1,
            "critical_count": 0,
        },
    }


def test_oat_failures_include_remediation_and_do_not_run_operations() -> None:
    result = evaluate_operational_acceptance([])
    assert result["status"] == "EVIDENCE_INCOMPLETE"
    assert result["percentage"] == 0
    assert all(check["remediation"] for check in result["checks"])
    assert result["restart_performed"] is False
    assert result["shutdown_performed"] is False
    assert result["deployment_performed"] is False


def test_complete_evidence_certifies_only_controlled_deployment_readiness() -> None:
    result = ProductionReadinessCertificationEngine(
        evidence=_evidence(),
        governance_snapshot=_governance(),
    ).evaluate()
    assert result["status"] == "CERTIFIED_FOR_CONTROLLED_DEPLOYMENT"
    assert result["certification_score"] == 100
    assert result["evidence_completeness"] == 100
    assert result["deployment_blockers"] == []
    assert result["deployment_authorized"] is False
    assert result["deployment_performed"] is False
    assert result["production_trading_certified"] is False
    assert result["endurance_readiness"]["synthetic_performance_claims"] is False
    assert result["disaster_recovery_readiness"]["restore_performed"] is False
    assert result["execution_posture"] == "DISABLED"
    assert result["execution_authority"] == "BLOCKED"


def test_missing_evidence_blocks_certification_without_fabrication() -> None:
    evidence = _evidence()[:-3]
    result = ProductionReadinessCertificationEngine(
        evidence=evidence,
        governance_snapshot=_governance(),
    ).evaluate()
    assert result["status"] == "NOT_CERTIFIED"
    assert result["deployment_blockers"]
    assert result["evidence_fabricated"] is False
    assert result["evidence_completeness"] < 100


def test_a4_reports_and_reports_center_registration(tmp_path) -> None:
    certification = ProductionReadinessCertificationEngine(
        evidence=_evidence(),
        governance_snapshot=_governance(),
    ).evaluate()
    reports = build_production_readiness_report_suite(certification)
    assert set(reports) == set(PRODUCTION_READINESS_REPORT_TITLES)
    assert len({report["report_id"] for report in reports.values()}) == len(reports)
    for report in reports.values():
        assert report["document"]["presentation"]["page_size"] == "A4"
        assert report["viewer_compatible"] is True
        assert report["deployment_authorized"] is False
        assert report["execution_allowed"] is False
    assert REPORT_CODES <= registered_producer_codes()
    for report_code in REPORT_CODES:
        definition = by_code(report_code)
        assert definition is not None
        assert definition.status == "AVAILABLE_WITH_LIMITATIONS"
        generated = produce(report_code, filters={}, repo_root=tmp_path)
        assert generated["report_status"] == "FAILED"
        assert generated["content"]["status"] == "EVIDENCE_UNAVAILABLE"
        assert generated["execution_allowed"] is False


def test_production_readiness_dashboard_is_admin_only_and_read_only() -> None:
    certification = ProductionReadinessCertificationEngine(
        evidence=_evidence(),
        governance_snapshot=_governance(),
    ).evaluate()
    state = {
        "authorization_context": {
            "authenticated": True,
            "active": True,
            "role": "SUPER_USER",
        },
        "reports_authorization": {},
        "production_readiness": certification,
    }
    html = render_mission_control_shell(state, active_section="production_readiness")
    for label in (
        "Production Readiness",
        "Certification Score",
        "Governance Score",
        "Broker Readiness",
        "Runtime Readiness",
        "Deployment Blockers",
        "Outstanding Risks",
        "Evidence Completeness",
    ):
        assert label in html
    assert "does not authorize deployment" in html
    assert "BLOCKED" in html
    denied = render_mission_control_shell({}, active_section="production_readiness")
    assert "Administrator authentication is required" in denied
    assert resolve_section_slug("production-readiness").key == "production_readiness"
    assert len(MISSION_CONTROL_SECTIONS) == 16
