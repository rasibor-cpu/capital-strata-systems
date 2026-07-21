"""A4 reports for Phase 179A.1 secret-authority migration."""

from __future__ import annotations

from typing import Any
import uuid

from backend.broker_reporting.page_layout import build_paginated_document
from backend.security.identity.authority_certification import certify_secret_authority
from backend.security.identity.authority_redirector import EnterpriseAuthorityRedirector
from backend.security.identity.identity_models import utc_now

AUTHORITY_REPORT_TITLES = {
    "secret_authority_certification": "Secret Authority Certification",
    "legacy_compatibility_audit": "Legacy Compatibility Audit",
    "ownership_coverage": "Secret Ownership Coverage",
    "vault_health": "Enterprise Vault Health",
    "migration_progress": "Secret Authority Migration Progress",
    "direct_access_violations": "Direct Credential Access Violations",
}


def build_authority_report(
    report_type: str,
    *,
    redirector: EnterpriseAuthorityRedirector,
) -> dict[str, Any]:
    key = str(report_type).lower()
    if key not in AUTHORITY_REPORT_TITLES:
        raise KeyError("AUTHORITY_REPORT_TYPE_UNKNOWN")
    certification = certify_secret_authority(redirector)
    sections = {
        "secret_authority_certification": [
            ("Certification", certification),
            ("Canonical Dependency Graph", redirector.dependency_graph()),
        ],
        "legacy_compatibility_audit": [
            ("Legacy Ownership", [
                row for row in certification["ownership"]
                if row["status"] == "LEGACY_COMPATIBILITY"
            ]),
            ("Direct Access", certification["direct_access_violations"]),
        ],
        "ownership_coverage": [
            ("Ownership Inventory", certification["ownership"]),
            ("Coverage", certification["migration"]),
        ],
        "vault_health": [
            ("Vault Health Score", certification["vault_health"]),
            ("Score Rationale", certification["vault_health"]["rationale"]),
        ],
        "migration_progress": [
            ("Migration Progress", certification["migration"]),
            ("Remaining Blockers", certification["blockers"]),
        ],
        "direct_access_violations": [
            ("Direct Access Violations", certification["direct_access_violations"]),
            ("Canonical Path", redirector.dependency_graph()),
        ],
    }[key]
    generated = utc_now()
    report_id = f"AUTH-{key.upper()}-{uuid.uuid4().hex[:10].upper()}"
    document = build_paginated_document(
        title=AUTHORITY_REPORT_TITLES[key],
        report_id=report_id,
        css_version="Phase-179A.1",
        commit_reference=None,
        generated_at=generated,
        executive_summary=[
            f"Certification outcome: {certification['outcome']}",
            f"Ownership coverage: {certification['migration']['coverage_pct']}%",
            f"Vault health score: {certification['vault_health']['score']}",
            f"Direct access violations: {len(certification['direct_access_violations'])}",
            "Execution authority: BLOCKED",
        ],
        sections=sections,
    )
    return {
        "schema_version": "css.secret_authority.report.v1",
        "report_type": key,
        "report_id": report_id,
        "generated_at": generated,
        "document": document.as_dict(),
        "viewer_compatible": True,
        "execution_allowed": False,
    }


def build_authority_report_suite(
    redirector: EnterpriseAuthorityRedirector,
) -> dict[str, dict[str, Any]]:
    return {
        report_type: build_authority_report(report_type, redirector=redirector)
        for report_type in AUTHORITY_REPORT_TITLES
    }


__all__ = [
    "AUTHORITY_REPORT_TITLES",
    "build_authority_report",
    "build_authority_report_suite",
]
