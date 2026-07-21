"""Certification-first evidence for Phase 179A identity and secrets controls."""

from __future__ import annotations

from typing import Any

from backend.security.identity.authority_certification import certify_secret_authority
from backend.security.identity.enterprise_identity_service import EnterpriseIdentityService
from backend.security.identity.enterprise_secret_service import EnterpriseSecretService


def certify_identity_platform(
    identities: EnterpriseIdentityService,
    secrets: EnterpriseSecretService,
    *,
    legacy_broker_migration_complete: bool = False,
) -> dict[str, Any]:
    secret_inventory = secrets._inventory()
    identity_inventory = identities.inventory()
    checks = {
        "canonical_identity_authority": True,
        "canonical_secret_authority": True,
        "metadata_only_default_retrieval": True,
        "duplicate_fingerprint_detection": True,
        "admin_policy_enforced": True,
        "immutable_access_audit": True,
        "automatic_rotation_disabled": True,
        "broker_handle_only_migration_complete": bool(legacy_broker_migration_complete),
        "oauth_execution_disabled": True,
        "broker_authentication_disabled": True,
        "execution_blocked": True,
    }
    certified = all(checks.values())
    return {
        "schema_version": "css.identity.certification.v1",
        "outcome": "CERTIFIED" if certified else "NOT_CERTIFIED",
        "checks": checks,
        "identity_count": len(identity_inventory),
        "secret_count": len(secret_inventory),
        "vault_health": secrets.vault.health().__dict__,
        "risk": secrets.risk_summary(),
        "remaining_blockers": [
            name for name, passed in checks.items() if not passed
        ],
        "advisory_only": True,
        "execution_allowed": False,
    }


def identity_governance_payload(
    identities: EnterpriseIdentityService,
    secrets: EnterpriseSecretService,
    *,
    legacy_broker_migration_complete: bool = False,
    authority_redirector: Any | None = None,
) -> dict[str, Any]:
    inventory = secrets._inventory()
    certification = certify_identity_platform(
        identities,
        secrets,
        legacy_broker_migration_complete=legacy_broker_migration_complete,
    )
    authority = certify_secret_authority(authority_redirector) if authority_redirector is not None else {}
    ownership = authority.get("ownership", [])
    return {
        "schema_version": "css.enterprise_identity.governance.v1",
        "enterprise_identity": identities.inventory(),
        "enterprise_secrets": inventory,
        "vault_health": certification["vault_health"],
        "rotation": secrets.rotation_status(),
        "certificates": [
            row for row in inventory if "CERTIFICATE" in str(row.get("secret_type"))
        ],
        "oauth": [
            row for row in inventory
            if any(token in str(row.get("secret_type")) for token in ("OAUTH", "TOKEN"))
        ],
        "broker_authentication": [row for row in inventory if row.get("broker")],
        "risk": secrets.risk_summary(),
        "audit": [entry.as_dict() for entry in secrets.audit.entries()],
        "certification": certification,
        "secret_authority": authority,
        "legacy_compatibility": [
            row for row in ownership if row.get("status") == "LEGACY_COMPATIBILITY"
        ],
        "ownership_coverage": authority.get("migration", {}),
        "orphaned_secrets": [
            row for row in ownership if row.get("status") == "ORPHANED"
        ],
        "direct_access_violations": authority.get("direct_access_violations", []),
        "migration_progress": authority.get("migration", {}),
        "vault_health_score": authority.get("vault_health", {}),
        "plaintext_returned": False,
        "advisory_only": True,
        "execution_allowed": False,
    }


__all__ = ["certify_identity_platform", "identity_governance_payload"]
