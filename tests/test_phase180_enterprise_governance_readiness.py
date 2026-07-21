"""Phase 180 — Enterprise Governance and certification readiness."""

from __future__ import annotations

from datetime import date

import pytest

from backend.certification.certification_engine import CertificationEngine
from backend.governance import (
    GOVERNANCE_REPORT_TITLES,
    EnterpriseGovernanceService,
    EnterpriseRisk,
    EnterpriseRiskRegister,
    EvidenceStatus,
    GovernanceDomain,
    GovernanceEvidence,
    RecoveryObjectives,
    RiskCategory,
    RiskRating,
    assess_iso_27001,
    build_governance_report_suite,
)
from backend.governance.business_continuity import BUSINESS_CONTINUITY_CONTROLS
from backend.governance.governance_certification import CERTIFICATION_FACETS
from backend.governance.iso_readiness import ISO_27001_CONTROLS, ISO_9001_CONTROLS
from backend.reports_center.producers import produce, registered_producer_codes
from backend.reports_center.registry import by_code
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS, resolve_section_slug


REPORT_CODES = {
    "enterprise_governance_readiness",
    "enterprise_iso_27001_readiness",
    "enterprise_iso_9001_readiness",
    "enterprise_business_continuity_readiness",
    "enterprise_risk_register",
    "enterprise_executive_certification_summary",
    "enterprise_compliance_dashboard",
    "enterprise_outstanding_certification_blockers",
}


def _evidence() -> list[GovernanceEvidence]:
    rows: list[GovernanceEvidence] = []
    used: set[tuple[str, str]] = set()

    def add(domain: GovernanceDomain, control: str) -> None:
        key = (domain.value, control)
        if key in used:
            return
        used.add(key)
        rows.append(
            GovernanceEvidence(
                evidence_id=f"E-{len(rows) + 1:04d}",
                domain=domain,
                control=control,
                status=EvidenceStatus.PRESENT,
                source="PHASE180_TEST_EVIDENCE",
                reference=f"evidence://phase180/{domain.value.lower()}/{control.lower()}",
                observed_at="2026-07-21T00:00:00+00:00",
                owner="governance-office",
                verified=True,
            )
        )

    iso_domains = {
        "AUDIT": GovernanceDomain.AUDIT,
        "BACKUP": GovernanceDomain.BUSINESS_CONTINUITY,
        "RECOVERY": GovernanceDomain.BUSINESS_CONTINUITY,
        "LOGGING": GovernanceDomain.OPERATIONS,
        "CHANGE_CONTROL": GovernanceDomain.OPERATIONS,
    }
    for control in ISO_27001_CONTROLS:
        add(iso_domains.get(control, GovernanceDomain.SECURITY), control)
    for control in ISO_9001_CONTROLS:
        add(GovernanceDomain.OPERATIONS, control)
    for control in BUSINESS_CONTINUITY_CONTROLS:
        if control != "RECOVERY_OBJECTIVES":
            add(GovernanceDomain.BUSINESS_CONTINUITY, control)
    for domain, control in CERTIFICATION_FACETS.values():
        add(domain, control)
    for domain in GovernanceDomain:
        add(domain, "DOMAIN_GOVERNANCE")
    return rows


def _risks() -> EnterpriseRiskRegister:
    return EnterpriseRiskRegister(
        EnterpriseRisk(
            risk_id=f"RISK-{index:03d}",
            category=category,
            title=f"{category.value.title()} governance risk",
            severity=RiskRating.HIGH if category is RiskCategory.SECURITY else RiskRating.MEDIUM,
            likelihood=RiskRating.MEDIUM,
            owner="enterprise-risk",
            mitigation="Maintain evidence-backed controls and quarterly review.",
            review_date=date(2026, 10, 1).isoformat(),
            certification_status="MITIGATION_IN_PROGRESS",
            evidence_references=(f"evidence://risk/{category.value.lower()}",),
        )
        for index, category in enumerate(RiskCategory, start=1)
    )


def _governance() -> EnterpriseGovernanceService:
    return EnterpriseGovernanceService(
        evidence=_evidence(),
        risks=_risks(),
        recovery_objectives=RecoveryObjectives(
            recovery_time_objective_minutes=60,
            recovery_point_objective_minutes=15,
            owner="business-continuity",
            last_reviewed="2026-07-21",
        ),
    )


def test_iso_readiness_requires_verified_evidence_and_never_claims_certification() -> None:
    incomplete = assess_iso_27001([])
    assert incomplete.percentage == 0
    assert incomplete.controls_missing == len(ISO_27001_CONTROLS)
    assert incomplete.formal_certification_claimed is False
    complete = assess_iso_27001(_evidence())
    assert complete.percentage == 100
    assert complete.formal_certification_claimed is False


def test_governance_continuity_risk_and_certification_snapshot() -> None:
    snapshot = _governance().snapshot()
    assert snapshot["governance_score"] == 100
    assert snapshot["iso_27001"]["percentage"] == 100
    assert snapshot["iso_9001"]["percentage"] == 100
    assert snapshot["business_continuity"]["percentage"] == 100
    assert snapshot["certification"]["status"] == "READY_FOR_FORMAL_REVIEW"
    assert snapshot["formal_certification_claimed"] is False
    assert snapshot["production_certified"] is False
    assert snapshot["enterprise_risk_summary"]["risk_count"] == len(RiskCategory)
    assert snapshot["execution_posture"] == "DISABLED"
    assert snapshot["execution_authority"] == "BLOCKED"


def test_risk_register_is_immutable_and_validated() -> None:
    risk = EnterpriseRisk(
        risk_id="RISK-DUPLICATE",
        category=RiskCategory.OPERATIONAL,
        title="Duplicate test risk",
        severity=RiskRating.MEDIUM,
        likelihood=RiskRating.LOW,
        owner="enterprise-risk",
        mitigation="Test duplicate prevention.",
        review_date="2026-10-01",
        certification_status="OPEN",
    )
    with pytest.raises(ValueError, match="DUPLICATE_ENTERPRISE_RISK_ID"):
        EnterpriseRiskRegister((risk, risk))
    register = _risks()
    first = register.inventory()
    first.clear()
    assert register.summary()["risk_count"] == len(RiskCategory)


def test_governance_reports_and_reports_center_registration(tmp_path) -> None:
    reports = build_governance_report_suite(_governance())
    assert set(reports) == set(GOVERNANCE_REPORT_TITLES)
    assert len({report["report_id"] for report in reports.values()}) == len(reports)
    for report in reports.values():
        assert report["document"]["presentation"]["page_size"] == "A4"
        assert report["viewer_compatible"] is True
        assert report["formal_certification_claimed"] is False
        assert report["execution_allowed"] is False
    assert REPORT_CODES <= registered_producer_codes()
    for report_code in REPORT_CODES:
        definition = by_code(report_code)
        assert definition is not None
        assert definition.status == "AVAILABLE_WITH_LIMITATIONS"
        result = produce(report_code, filters={}, repo_root=tmp_path)
        assert result["report_status"] == "FAILED"
        assert result["content"]["status"] == "EVIDENCE_UNAVAILABLE"
        assert result["execution_allowed"] is False


def test_executive_governance_dashboard_is_administrative_and_read_only() -> None:
    state = {
        "authorization_context": {
            "authenticated": True,
            "active": True,
            "role": "SUPER_USER",
        },
        "reports_authorization": {},
        "enterprise_governance": _governance().snapshot(),
    }
    html = render_mission_control_shell(state, active_section="enterprise_governance")
    for label in (
        "Executive Governance",
        "Overall Readiness",
        "ISO 27001 Readiness",
        "Business Continuity",
        "Enterprise Risk Register",
        "Outstanding Certification Blockers",
    ):
        assert label in html
    assert "not ISO certification" in html
    assert "BLOCKED" in html
    denied = render_mission_control_shell({}, active_section="enterprise_governance")
    assert "Administrator authentication is required" in denied
    assert resolve_section_slug("enterprise-governance").key == "enterprise_governance"
    assert len(MISSION_CONTROL_SECTIONS) == 16


def test_certification_engine_extension_uses_only_supplied_evidence() -> None:
    result = CertificationEngine().evaluate_enterprise_governance(_evidence())
    assert result["status"] == "READY_FOR_FORMAL_REVIEW"
    assert result["evidence_fabricated"] is False
    assert result["formal_certification_claimed"] is False
