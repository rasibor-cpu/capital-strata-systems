"""A4 paginated reports for Enterprise Identity & Secrets governance."""

from __future__ import annotations

from typing import Any
import uuid

from backend.broker_reporting.page_layout import build_paginated_document
from backend.security.identity.enterprise_identity_service import EnterpriseIdentityService
from backend.security.identity.enterprise_secret_service import EnterpriseSecretService
from backend.security.identity.identity_certification import certify_identity_platform
from backend.security.identity.identity_models import utc_now


REPORT_TITLES = {
    "identity_certification": "Enterprise Identity Certification",
    "vault_certification": "Enterprise Vault Certification",
    "secret_inventory": "Enterprise Secret Inventory",
    "rotation_readiness": "Secret Rotation Readiness",
    "compliance": "Identity and Secrets Compliance",
    "credential_risk": "Credential Risk",
}


def build_identity_report(
    report_type: str,
    *,
    identities: EnterpriseIdentityService,
    secrets: EnterpriseSecretService,
    legacy_broker_migration_complete: bool = False,
) -> dict[str, Any]:
    key = str(report_type).lower()
    if key not in REPORT_TITLES:
        raise KeyError("IDENTITY_REPORT_TYPE_UNKNOWN")
    generated = utc_now()
    certification = certify_identity_platform(
        identities,
        secrets,
        legacy_broker_migration_complete=legacy_broker_migration_complete,
    )
    inventory = secrets._inventory()
    payloads = {
        "identity_certification": [
            ("Certification", certification),
            ("Identity Inventory", identities.inventory()),
        ],
        "vault_certification": [
            ("Vault Health", certification["vault_health"]),
            ("Certification Checks", certification["checks"]),
        ],
        "secret_inventory": [
            ("Secret Inventory", inventory),
            ("Classifications", _classification_summary(inventory)),
        ],
        "rotation_readiness": [
            ("Rotation Status", secrets.rotation_status()),
            ("Dependency Graph", secrets.dependencies.as_dict()),
        ],
        "compliance": [
            ("Certification", certification),
            ("Access Audit", [entry.as_dict() for entry in secrets.audit.entries()]),
        ],
        "credential_risk": [
            ("Risk Summary", secrets.risk_summary()),
            ("Rotation Impact", [
                secrets.rotation_impact(row["secret_uuid"]) for row in inventory
            ]),
        ],
    }
    report_id = f"IDSEC-{key.upper()}-{uuid.uuid4().hex[:10].upper()}"
    document = build_paginated_document(
        title=REPORT_TITLES[key],
        report_id=report_id,
        css_version="Phase-179A",
        commit_reference=None,
        generated_at=generated,
        executive_summary=[
            f"Certification outcome: {certification['outcome']}",
            f"Identity count: {certification['identity_count']}",
            f"Secret count: {certification['secret_count']}",
            "Secret values returned: false",
            "Execution authority: BLOCKED",
        ],
        sections=payloads[key],
    )
    return {
        "schema_version": "css.identity.report.v1",
        "report_type": key,
        "report_id": report_id,
        "generated_at": generated,
        "document": document.as_dict(),
        "viewer_compatible": True,
        "advisory_only": True,
        "execution_allowed": False,
    }


def build_identity_report_suite(
    *,
    identities: EnterpriseIdentityService,
    secrets: EnterpriseSecretService,
) -> dict[str, dict[str, Any]]:
    return {
        report_type: build_identity_report(
            report_type,
            identities=identities,
            secrets=secrets,
        )
        for report_type in REPORT_TITLES
    }


def _classification_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        label = str(row.get("classification") or "UNKNOWN")
        summary[label] = summary.get(label, 0) + 1
    return summary


__all__ = ["REPORT_TITLES", "build_identity_report", "build_identity_report_suite"]
