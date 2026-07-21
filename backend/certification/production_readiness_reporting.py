"""A4 Phase 181 production-readiness reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from backend.broker_reporting.page_layout import build_paginated_document

PRODUCTION_READINESS_REPORT_TITLES = {
    "production_readiness": "Production Readiness",
    "operational_acceptance": "Operational Acceptance",
    "endurance_readiness": "Endurance Readiness",
    "disaster_recovery_readiness": "Disaster Recovery Readiness",
    "deployment_readiness": "Deployment Readiness",
    "production_outstanding_blockers": "Outstanding Blockers",
    "final_certification_summary": "Final Certification Summary",
}


def build_production_readiness_report(
    report_type: str,
    *,
    certification: dict[str, Any],
) -> dict[str, Any]:
    key = str(report_type).lower()
    if key not in PRODUCTION_READINESS_REPORT_TITLES:
        raise KeyError("PRODUCTION_READINESS_REPORT_TYPE_UNKNOWN")
    sections = {
        "production_readiness": [
            ("Platform Certification", certification["platform_certification"]),
            ("Readiness Summary", _summary(certification)),
        ],
        "operational_acceptance": [
            ("Operational Acceptance", certification["operational_acceptance"]),
        ],
        "endurance_readiness": [
            ("Endurance Readiness", certification["endurance_readiness"]),
        ],
        "disaster_recovery_readiness": [
            (
                "Disaster Recovery Readiness",
                certification["disaster_recovery_readiness"],
            ),
        ],
        "deployment_readiness": [
            ("Deployment Readiness", certification["deployment_readiness"]),
        ],
        "production_outstanding_blockers": [
            ("Outstanding Blockers", certification["deployment_blockers"]),
            ("Outstanding Risks", certification["outstanding_risks"]),
        ],
        "final_certification_summary": [
            ("Certification Summary", certification),
            ("Evidence Inventory", certification["evidence_inventory"]),
        ],
    }[key]
    generated = datetime.now(timezone.utc).isoformat()
    report_id = f"PRD-{key.upper()}-{uuid.uuid4().hex[:10].upper()}"
    document = build_paginated_document(
        title=PRODUCTION_READINESS_REPORT_TITLES[key],
        report_id=report_id,
        css_version="Phase-181",
        commit_reference=None,
        generated_at=generated,
        executive_summary=[
            f"Certification status: {certification['status']}",
            f"Certification score: {certification['certification_score']}%",
            f"Evidence completeness: {certification['evidence_completeness']}%",
            f"Deployment blockers: {len(certification['deployment_blockers'])}",
            "Deployment authorized: false",
            "Execution posture: DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY",
        ],
        sections=sections,
    )
    return {
        "schema_version": "css.production_readiness.report.v1",
        "report_type": key,
        "report_id": report_id,
        "generated_at": generated,
        "document": document.as_dict(),
        "viewer_compatible": True,
        "page_size": "A4",
        "deployment_authorized": False,
        "execution_allowed": False,
    }


def build_production_readiness_report_suite(
    certification: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        report_type: build_production_readiness_report(
            report_type,
            certification=certification,
        )
        for report_type in PRODUCTION_READINESS_REPORT_TITLES
    }


def _summary(certification: dict[str, Any]) -> dict[str, Any]:
    return {
        "certification_score": certification["certification_score"],
        "governance_score": certification["governance_score"],
        "broker_readiness": certification["broker_readiness"],
        "runtime_readiness": certification["runtime_readiness"],
        "deployment_blockers": certification["deployment_blockers"],
        "outstanding_risks": certification["outstanding_risks"],
        "evidence_completeness": certification["evidence_completeness"],
    }


__all__ = [
    "PRODUCTION_READINESS_REPORT_TITLES",
    "build_production_readiness_report",
    "build_production_readiness_report_suite",
]
