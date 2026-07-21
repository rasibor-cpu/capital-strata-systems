"""A4 CSS Enterprise RC1 certification reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from backend.broker_reporting.page_layout import build_paginated_document

RC1_REPORT_TITLES = {
    "rc1_certification_summary": "RC1 Certification Summary",
    "rc1_readiness_scorecard": "RC1 Readiness Scorecard",
    "rc1_regression_evidence": "Regression Evidence",
    "rc1_compile_evidence": "Compile Evidence",
    "rc1_runtime_evidence": "Runtime Evidence",
    "rc1_outstanding_blockers": "Outstanding Blockers",
}


def build_rc1_report(
    report_type: str,
    *,
    certification: dict[str, Any],
) -> dict[str, Any]:
    key = str(report_type).lower()
    if key not in RC1_REPORT_TITLES:
        raise KeyError("RC1_REPORT_TYPE_UNKNOWN")
    sections = {
        "rc1_certification_summary": [
            ("Certification", certification),
            ("Tagging Readiness", _tagging(certification)),
        ],
        "rc1_readiness_scorecard": [
            ("Executive Scorecard", certification["scorecard"]),
            ("Certification Gates", certification["requirements"]),
        ],
        "rc1_regression_evidence": [
            ("Pytest Command Evidence", _area(certification, "PYTEST")),
            ("Evidence Inventory", certification["evidence_inventory"]),
        ],
        "rc1_compile_evidence": [
            ("Compileall Command Evidence", _area(certification, "COMPILEALL")),
        ],
        "rc1_runtime_evidence": [
            ("Runtime Evidence", _area(certification, "RUNTIME")),
            ("Runtime Gate", {"passed": certification["requirements"]["RUNTIME"]}),
        ],
        "rc1_outstanding_blockers": [
            ("Outstanding Blockers", certification["outstanding_blockers"]),
        ],
    }[key]
    generated = datetime.now(timezone.utc).isoformat()
    report_id = f"RC1-{key.upper()}-{uuid.uuid4().hex[:10].upper()}"
    document = build_paginated_document(
        title=RC1_REPORT_TITLES[key],
        report_id=report_id,
        css_version="Enterprise-RC1",
        commit_reference=None,
        generated_at=generated,
        executive_summary=[
            f"Overall RC1 status: {certification['status']}",
            f"Certification readiness: {certification['scorecard']['certification_readiness']}%",
            f"Outstanding blockers: {len(certification['outstanding_blockers'])}",
            f"Tag recommendation: {certification['tag_recommendation'] or 'NOT_RECOMMENDED'}",
            "Execution posture: DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY",
        ],
        sections=sections,
    )
    return {
        "schema_version": "css.enterprise.rc1.report.v1",
        "report_type": key,
        "report_id": report_id,
        "generated_at": generated,
        "document": document.as_dict(),
        "viewer_compatible": True,
        "page_size": "A4",
        "tag_created": False,
        "deployment_authorized": False,
        "execution_allowed": False,
    }


def build_rc1_report_suite(
    certification: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        key: build_rc1_report(key, certification=certification)
        for key in RC1_REPORT_TITLES
    }


def _area(certification: dict[str, Any], area: str) -> list[dict[str, Any]]:
    return [
        row
        for row in certification["evidence_inventory"]
        if str(row.get("area")).upper() == area
    ]


def _tagging(certification: dict[str, Any]) -> dict[str, Any]:
    return {
        "recommended_tag": certification["tag_recommendation"],
        "recommendation_allowed": certification["status"] == "CERTIFIED",
        "tag_created": False,
    }


__all__ = ["RC1_REPORT_TITLES", "build_rc1_report", "build_rc1_report_suite"]
