"""Read-only Mission Control surface for Phase 179A."""

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


def _count(value: object) -> object:
    if isinstance(value, (list, dict, tuple, set)):
        return len(value)
    return "EVIDENCE_MISSING"


def render(state: dict) -> str:
    auth = state.get("authorization_context") if isinstance(state.get("authorization_context"), dict) else {}
    if not (
        auth.get("authenticated")
        and auth.get("active")
        and str(auth.get("role") or "").upper() in {"SUPER_USER", "ADMIN"}
    ):
        return (
            page_header("Enterprise Identity & Secrets", "Canonical identity and secret metadata.")
            + warning_banner("Administrator authentication is required.")
        )
    raw = state.get("identity_governance")
    data = redact_value(raw if isinstance(raw, dict) else {})
    identities = data.get("enterprise_identity") if isinstance(data.get("enterprise_identity"), list) else []
    secrets = data.get("enterprise_secrets") if isinstance(data.get("enterprise_secrets"), list) else []
    vault = data.get("vault_health") if isinstance(data.get("vault_health"), dict) else {}
    rotation = data.get("rotation") if isinstance(data.get("rotation"), dict) else {}
    certificates = data.get("certificates") if isinstance(data.get("certificates"), list) else []
    oauth = data.get("oauth") if isinstance(data.get("oauth"), list) else []
    broker_auth = data.get("broker_authentication") if isinstance(data.get("broker_authentication"), list) else []
    risk = data.get("risk") if isinstance(data.get("risk"), dict) else {}
    audit = data.get("audit") if isinstance(data.get("audit"), list) else []
    authority = data.get("secret_authority") if isinstance(data.get("secret_authority"), dict) else {}
    compatibility = data.get("legacy_compatibility") if isinstance(data.get("legacy_compatibility"), list) else []
    ownership = data.get("ownership_coverage") if isinstance(data.get("ownership_coverage"), dict) else {}
    orphaned = data.get("orphaned_secrets") if isinstance(data.get("orphaned_secrets"), list) else []
    violations = data.get("direct_access_violations") if isinstance(data.get("direct_access_violations"), list) else []
    migration = data.get("migration_progress") if isinstance(data.get("migration_progress"), dict) else {}
    health_score = data.get("vault_health_score") if isinstance(data.get("vault_health_score"), dict) else {}
    return (
        page_header(
            "Enterprise Identity & Secrets",
            "Certification-first identity, vault, rotation, authentication, risk, and audit metadata. Read-only.",
        )
        + '<nav class="mc-page-jump" aria-label="Enterprise Identity sections">'
          '<a href="#mc-id-status">Status</a>'
          '<a href="#mc-id-risk">Risk</a>'
          '<a href="#mc-id-migration">Migration</a>'
          '<a href="#mc-id-evidence">Evidence</a>'
          '</nav>'
        + metric_grid(
            (
                ("Vault", vault.get("status", "UNCONFIGURED"), vault.get("status", "UNCONFIGURED")),
                ("Vault Health Score", health_score.get("score", "EVIDENCE_MISSING"), health_score.get("status", "EVIDENCE_MISSING")),
                ("Identities", _count(identities), "neutral"),
                ("Managed Entries", _count(secrets), "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority mc-id-priority",
            aria_label="Enterprise Identity priority",
        )
        + metric_grid(
            (
                ("Rotation Reminders", _count(rotation.get("reminders")), "warning" if rotation.get("reminders") else "neutral"),
                ("High Risk", risk.get("high_risk_count", "EVIDENCE_MISSING"), risk.get("high_risk_count", "EVIDENCE_MISSING")),
                ("Orphaned Entries", _count(orphaned), "warning" if orphaned else "neutral"),
                ("Access Violations", _count(violations), "warning" if violations else "neutral"),
            ),
            css_class="mc-metric-grid mc-metric-grid-secondary",
            aria_label="Enterprise Identity secondary metrics",
        )
        + '<div class="mc-operator-stack">'
        + _anchor_panel("mc-id-status", detail_table("Identity & Vault Snapshot", {
            "identity_count": _count(identities),
            "managed_entry_count": _count(secrets),
            "vault_status": vault.get("status", "UNCONFIGURED"),
            "certificate_count": _count(certificates),
            "oauth_registration_count": _count(oauth),
            "broker_auth_record_count": _count(broker_auth),
        }))
        + _anchor_panel("mc-id-risk", detail_table("Risk Snapshot", {
            "high_risk_count": risk.get("high_risk_count", "EVIDENCE_MISSING"),
            "orphaned_entry_count": _count(orphaned),
            "direct_access_violation_count": _count(violations),
            "audit_event_count": _count(audit),
        }))
        + _anchor_panel("mc-id-migration", detail_table("Migration Snapshot", {
            "migration_status": migration.get("status", "EVIDENCE_MISSING"),
            "ownership_coverage": ownership.get("status", ownership.get("coverage", "EVIDENCE_MISSING")),
            "legacy_compatibility_count": _count(compatibility),
            "rotation_reminder_count": _count(rotation.get("reminders")),
        }))
        + _evidence_panel("mc-id-evidence", "Show identity and vault metadata", detail_table("Enterprise Identity", identities) + detail_table("Vault Health", vault))
        + _evidence_panel("mc-id-rotation", "Show rotation and certificate metadata", detail_table("Rotation", rotation) + detail_table("Certificates", certificates))
        + _evidence_panel("mc-id-auth", "Show authentication registration metadata", detail_table("OAuth", oauth) + detail_table("Broker Authentication", broker_auth))
        + _evidence_panel("mc-id-risk-evidence", "Show risk and audit metadata", detail_table("Risk", risk) + detail_table("Audit", audit) + detail_table("Orphaned Entries", orphaned) + detail_table("Direct Access Violations", violations))
        + _evidence_panel("mc-id-governance", "Show authority and migration metadata", detail_table("Secret Authority", authority) + detail_table("Legacy Compatibility", compatibility) + detail_table("Ownership Coverage", ownership) + detail_table("Migration Progress", migration) + detail_table("Vault Health Score", health_score))
        + '</div>'
    )


__all__ = ["render"]
