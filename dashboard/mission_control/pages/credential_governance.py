"""Metadata-only Mission Control projection for ESMS-001/002."""

from __future__ import annotations

from backend.security.vault_redaction import redact_value
from dashboard.mission_control.pages._components import (
    detail_table,
    metric_grid,
    page_header,
    split_panels,
    warning_banner,
)


def render(state: dict) -> str:
    auth = state.get("authorization_context") if isinstance(state.get("authorization_context"), dict) else {}
    allowed = bool(
        auth.get("authenticated")
        and auth.get("active")
        and str(auth.get("role") or "").upper() in {"SUPER_USER", "ADMIN"}
    )
    if not allowed:
        return (
            page_header(
                "Credential Governance",
                "Enterprise Secret Management and credential dependency governance.",
            )
            + warning_banner("Administrator authentication is required to view credential metadata.")
        )
    raw = state.get("credential_governance")
    governance = redact_value(raw if isinstance(raw, dict) else {})
    health = governance.get("vault_health") if isinstance(governance.get("vault_health"), dict) else {}
    inventory = governance.get("credential_inventory") if isinstance(governance.get("credential_inventory"), list) else []
    rotation = governance.get("rotation_queue") if isinstance(governance.get("rotation_queue"), list) else []
    expiring = governance.get("expiring_soon") if isinstance(governance.get("expiring_soon"), list) else []
    audit = governance.get("audit_events") if isinstance(governance.get("audit_events"), list) else []
    dependencies = governance.get("dependency_graph") if isinstance(governance.get("dependency_graph"), dict) else {}
    compliance = governance.get("compliance") if isinstance(governance.get("compliance"), dict) else {}
    selected = governance.get("selected_credential") if isinstance(governance.get("selected_credential"), dict) else {}
    return (
        page_header(
            "Credential Governance",
            "ESMS-001 vault health, ESMS-002 dependencies, rotation, audit, and compliance metadata. Secrets are never displayed.",
        )
        + metric_grid(
            (
                ("Vault Health", health.get("status", "UNCONFIGURED"), health.get("status", "neutral")),
                ("Credentials", len(inventory), "neutral"),
                ("Rotation Queue", len(rotation), "neutral"),
                ("Expiring Soon", len(expiring), "warning" if expiring else "normal"),
                ("Compliance", compliance.get("outcome", "EVIDENCE_PENDING"), compliance.get("outcome", "neutral")),
            )
        )
        + split_panels(
            detail_table("Credential Inventory", inventory),
            detail_table("Selected Credential", {
                key: selected.get(key)
                for key in (
                    "vcid",
                    "broker",
                    "owner",
                    "health",
                    "rotation_due",
                    "dependencies",
                    "audit_history",
                    "validation_history",
                    "fingerprint",
                )
            }),
            detail_table("Rotation Queue", rotation),
            detail_table("Expiring Soon", expiring),
            detail_table("Audit Events", audit),
            detail_table("Dependency Graph", dependencies),
            detail_table("Compliance Status", compliance),
        )
    )


__all__ = ["render"]
