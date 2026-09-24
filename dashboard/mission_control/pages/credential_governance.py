"""Metadata-only Mission Control projection for ESMS-001/002."""

from __future__ import annotations

from backend.security.vault_redaction import redact_value
from dashboard.mission_control.pages._components import (
    detail_table,
    metric_grid,
    page_header,
    warning_banner,
)


def _anchor_panel(anchor: str, content: str) -> str:
    return f'<div class="mc-section-anchor" id="{anchor}">{content}</div>'


def _evidence_panel(anchor: str, title: str, content: str) -> str:
    return (
        f'<div class="mc-section-anchor mc-evidence-disclosure" id="{anchor}">'
        f'<details><summary>{title}</summary>{content}</details>'
        '</div>'
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
        + '<nav class="mc-page-jump" aria-label="Credential Governance sections">'
          '<a href="#mc-cred-status">Status</a>'
          '<a href="#mc-cred-rotation">Rotation</a>'
          '<a href="#mc-cred-compliance">Compliance</a>'
          '<a href="#mc-cred-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Vault Health", health.get("status", "UNCONFIGURED"), health.get("status", "UNCONFIGURED")),
                ("Compliance", compliance.get("outcome", "EVIDENCE_PENDING"), compliance.get("outcome", "EVIDENCE_PENDING")),
                ("Credentials", len(inventory), "neutral"),
                ("Expiring Soon", len(expiring), "warning" if expiring else "normal"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-cred-priority",
            aria_label="Credential Governance priority",
        )
        + metric_grid(
            (
                ("Rotation Queue", len(rotation), "warning" if rotation else "normal"),
                ("Audit Events", len(audit), "neutral"),
                ("Dependencies", len(dependencies), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Credential Governance secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-cred-status", detail_table("Credential Governance Snapshot", {
            "vault_health": health.get("status", "UNCONFIGURED"),
            "credential_count": len(inventory),
            "compliance": compliance.get("outcome", "EVIDENCE_PENDING"),
        }))
        + _anchor_panel("mc-cred-rotation", detail_table("Rotation Snapshot", {
            "rotation_queue_count": len(rotation),
            "expiring_soon_count": len(expiring),
        }))
        + _anchor_panel("mc-cred-compliance", detail_table("Compliance Snapshot", {
            "outcome": compliance.get("outcome", "EVIDENCE_PENDING"),
            "audit_event_count": len(audit),
            "dependency_node_count": len(dependencies),
        }))
        + _evidence_panel("mc-cred-evidence", "Show credential inventory metadata", detail_table("Credential Inventory", inventory))
        + _evidence_panel("mc-cred-selected", "Show selected credential metadata", detail_table("Selected Credential", {
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
        }))
        + _evidence_panel("mc-cred-rotation-evidence", "Show rotation and expiry metadata", detail_table("Rotation Queue", rotation) + detail_table("Expiring Soon", expiring))
        + _evidence_panel("mc-cred-audit", "Show audit and dependency metadata", detail_table("Audit Events", audit) + detail_table("Dependency Graph", dependencies))
        + _evidence_panel("mc-cred-compliance-evidence", "Show compliance metadata", detail_table("Compliance Status", compliance))
        + '</div>'
    )


__all__ = ["render"]
