"""A4 Enterprise Governance readiness reports."""

from __future__ import annotations

import uuid
from typing import Any

from backend.broker_reporting.page_layout import build_paginated_document
from backend.governance.governance_models import utc_now
from backend.governance.governance_service import EnterpriseGovernanceService

GOVERNANCE_REPORT_TITLES = {
    "governance_readiness": "Governance Readiness",
    "iso_27001_readiness": "ISO 27001 Readiness",
    "iso_9001_readiness": "ISO 9001 Readiness",
    "business_continuity_readiness": "Business Continuity Readiness",
    "enterprise_risk_register": "Enterprise Risk Register",
    "executive_certification_summary": "Executive Certification Summary",
    "compliance_dashboard": "Compliance Dashboard",
    "outstanding_certification_blockers": "Outstanding Certification Blockers",
}


def build_governance_report(
    report_type: str,
    *,
    governance: EnterpriseGovernanceService,
) -> dict[str, Any]:
    key = str(report_type).lower()
    if key not in GOVERNANCE_REPORT_TITLES:
        raise KeyError("GOVERNANCE_REPORT_TYPE_UNKNOWN")
    snapshot = governance.snapshot()
    sections = {
        "governance_readiness": [
            ("Governance Domains", snapshot["domains"]),
            ("Evidence Inventory", snapshot["evidence_inventory"]),
        ],
        "iso_27001_readiness": [
            ("ISO 27001 Readiness", snapshot["iso_27001"]),
        ],
        "iso_9001_readiness": [
            ("ISO 9001 Readiness", snapshot["iso_9001"]),
        ],
        "business_continuity_readiness": [
            ("Business Continuity", snapshot["business_continuity"]),
        ],
        "enterprise_risk_register": [
            ("Risk Summary", snapshot["enterprise_risk_summary"]),
            ("Risk Register", snapshot["enterprise_risk_register"]),
        ],
        "executive_certification_summary": [
            ("Certification Readiness", snapshot["certification"]),
            ("Executive Metrics", _executive_metrics(snapshot)),
        ],
        "compliance_dashboard": [
            ("Compliance Posture", _compliance(snapshot)),
            ("ISO Readiness", {
                "iso_27001": snapshot["iso_27001"]["percentage"],
                "iso_9001": snapshot["iso_9001"]["percentage"],
            }),
        ],
        "outstanding_certification_blockers": [
            ("Outstanding Blockers", snapshot["outstanding_blockers"]),
            ("Certification Evidence", snapshot["certification"]),
        ],
    }[key]
    generated = utc_now()
    report_id = f"GOV-{key.upper()}-{uuid.uuid4().hex[:10].upper()}"
    document = build_paginated_document(
        title=GOVERNANCE_REPORT_TITLES[key],
        report_id=report_id,
        css_version="Phase-180",
        commit_reference=None,
        generated_at=generated,
        executive_summary=[
            f"Overall readiness: {snapshot['overall_certification_readiness']}%",
            f"Governance score: {snapshot['governance_score']}%",
            f"Outstanding blockers: {len(snapshot['outstanding_blockers'])}",
            "Formal certification claimed: false",
            "Execution posture: DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY",
        ],
        sections=sections,
    )
    return {
        "schema_version": "css.enterprise_governance.report.v1",
        "report_type": key,
        "report_id": report_id,
        "generated_at": generated,
        "document": document.as_dict(),
        "viewer_compatible": True,
        "page_size": "A4",
        "formal_certification_claimed": False,
        "execution_allowed": False,
    }


def build_governance_report_suite(
    governance: EnterpriseGovernanceService,
) -> dict[str, dict[str, Any]]:
    return {
        report_type: build_governance_report(report_type, governance=governance)
        for report_type in GOVERNANCE_REPORT_TITLES
    }


def _executive_metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall_certification_readiness": snapshot["overall_certification_readiness"],
        "governance_score": snapshot["governance_score"],
        "broker_readiness": snapshot["broker_readiness"],
        "runtime_readiness": snapshot["runtime_readiness"],
        "security_posture": snapshot["security_posture"],
        "compliance_posture": snapshot["compliance_posture"],
        "risk_summary": snapshot["enterprise_risk_summary"],
    }


def _compliance(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": snapshot["compliance_posture"],
        "certification": snapshot["certification"],
        "formal_certification_claimed": False,
    }


__all__ = [
    "GOVERNANCE_REPORT_TITLES",
    "build_governance_report",
    "build_governance_report_suite",
]
