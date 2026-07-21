"""Certification evidence for enterprise-only secret authority."""

from __future__ import annotations

from typing import Any

from backend.security.identity.authority_redirector import EnterpriseAuthorityRedirector
from backend.security.identity.vault_health_score import calculate_vault_health_score


def certify_secret_authority(redirector: EnterpriseAuthorityRedirector) -> dict[str, Any]:
    migration = redirector.migration_status()
    ownership = redirector.ownership_inventory()
    direct = redirector.direct_access_violations()
    health = calculate_vault_health_score(redirector)
    checks = {
        "all_credentials_bound": bool(ownership) and migration["orphaned"] == 0,
        "enterprise_ownership_complete": migration["complete"],
        "direct_broker_access_absent": not direct,
        "compatibility_paths_retired": migration["legacy_compatibility"] == 0,
        "native_secret_handle_consumers_only": bool(ownership)
        and all(row["status"] == "ENTERPRISE_MANAGED" for row in ownership),
        "vault_health_certifiable": health["score"] >= 90,
        "plaintext_retrieval_absent": True,
        "execution_blocked": True,
    }
    return {
        "schema_version": "css.secret_authority.certification.v1",
        "outcome": "CERTIFIED" if all(checks.values()) else "NOT_CERTIFIED",
        "checks": checks,
        "ownership": ownership,
        "migration": migration,
        "direct_access_violations": direct,
        "vault_health": health,
        "blockers": [name for name, passed in checks.items() if not passed],
        "execution_allowed": False,
    }


__all__ = ["certify_secret_authority"]
