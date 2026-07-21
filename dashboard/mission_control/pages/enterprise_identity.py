"""Read-only Mission Control surface for Phase 179A."""

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
        + metric_grid(
            (
                ("Identities", len(identities), "neutral"),
                ("Secrets", len(secrets), "neutral"),
                ("Vault", vault.get("status", "UNCONFIGURED"), vault.get("status", "neutral")),
                ("Rotation Reminders", len(rotation.get("reminders", [])), "warning"),
                ("High Risk", risk.get("high_risk_count", 0), "warning"),
                ("Vault Health Score", health_score.get("score", 0), health_score.get("status", "neutral")),
            )
        )
        + split_panels(
            detail_table("Enterprise Identity", identities),
            detail_table("Enterprise Secrets", secrets),
            detail_table("Vault Health", vault),
            detail_table("Rotation", rotation),
            detail_table("Certificates", certificates),
            detail_table("OAuth", oauth),
            detail_table("Broker Authentication", broker_auth),
            detail_table("Secret Inventory", secrets),
            detail_table("Risk", risk),
            detail_table("Audit", audit),
            detail_table("Secret Authority", authority),
            detail_table("Legacy Compatibility", compatibility),
            detail_table("Ownership Coverage", ownership),
            detail_table("Orphaned Secrets", orphaned),
            detail_table("Direct Access Violations", violations),
            detail_table("Migration Progress", migration),
            detail_table("Vault Health Score", health_score),
        )
    )


__all__ = ["render"]
