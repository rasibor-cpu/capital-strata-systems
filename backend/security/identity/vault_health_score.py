"""Canonical 0-100 Enterprise Vault Health Score."""

from __future__ import annotations

from typing import Any

from backend.security.identity.authority_redirector import (
    EnterpriseAuthorityRedirector,
    OwnershipStatus,
)


def calculate_vault_health_score(redirector: EnterpriseAuthorityRedirector) -> dict[str, Any]:
    service = redirector.service
    inventory = service._inventory()
    ownership = redirector.ownership_inventory()
    migration = redirector.migration_status()
    direct = redirector.direct_access_violations()
    fingerprints = [row["fingerprint"] for row in inventory]
    duplicate_count = len(fingerprints) - len(set(fingerprints))
    rotation = service.rotation_status()
    expired = sum(row["effective_status"] == "EXPIRED" for row in rotation["secrets"])
    rotation_due = sum(row["effective_status"] == "ROTATION_DUE" for row in rotation["secrets"])
    orphaned = sum(row["status"] == OwnershipStatus.ORPHANED.value for row in ownership)
    policy_denials = sum(entry.result == "DENIED" for entry in service.audit.entries())
    registered_events = sum(
        event.event_type == "SECRET_REGISTERED" and event.result == "SUCCESS"
        for event in service.events.snapshot()
    )
    audit_coverage = min(1.0, registered_events / len(inventory)) if inventory else 1.0
    vault_health = service.vault.health()

    factors = {
        "ownership_coverage": {
            "weight": 25,
            "earned": round(25 * float(migration["coverage_pct"]) / 100.0, 2),
            "value": migration["coverage_pct"],
        },
        "duplicate_fingerprints": {
            "weight": 10,
            "earned": 10 if duplicate_count == 0 else 0,
            "value": duplicate_count,
        },
        "expired_secrets": {
            "weight": 10,
            "earned": 10 if expired == 0 else max(0, 10 - expired * 2),
            "value": expired,
        },
        "rotation_compliance": {
            "weight": 10,
            "earned": 10 if rotation_due == 0 else max(0, 10 - rotation_due * 2),
            "value": rotation_due,
        },
        "orphaned_secrets": {
            "weight": 10,
            "earned": 10 if orphaned == 0 else max(0, 10 - orphaned * 2),
            "value": orphaned,
        },
        "audit_coverage": {
            "weight": 10,
            "earned": round(10 * audit_coverage, 2),
            "value": round(100 * audit_coverage, 2),
        },
        "policy_violations": {
            "weight": 10,
            "earned": 10 if policy_denials == 0 else max(0, 10 - policy_denials),
            "value": policy_denials,
        },
        "cryptographic_posture": {
            "weight": 10,
            "earned": 10 if vault_health.integrity_verified else 0,
            "value": vault_health.status,
        },
        "unresolved_legacy_paths": {
            "weight": 5,
            "earned": 5 if not direct else 0,
            "value": len(direct),
        },
    }
    score = round(sum(float(row["earned"]) for row in factors.values()), 2)
    return {
        "score": max(0.0, min(100.0, score)),
        "status": "HEALTHY" if score >= 90 else "DEGRADED" if score >= 70 else "BLOCKED",
        "factors": factors,
        "rationale": [
            f"{name}: {row['earned']}/{row['weight']} (observed={row['value']})"
            for name, row in factors.items()
        ],
        "execution_allowed": False,
    }


__all__ = ["calculate_vault_health_score"]
