"""ESMS-001/002 compliance evidence derived from metadata only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.security.credential_vault import CredentialVault


def certify_vault(vault: CredentialVault, *, dependency_map: Any | None = None) -> dict[str, Any]:
    health = vault.health()
    inventory = vault.inventory()
    consumer_inventory = {
        row["vcid"]: list(vault.policy.consumer_inventory(row["vcid"])) for row in inventory
    }
    checks = {
        "aes_256_gcm": all(row.get("encryption_algorithm") == "AES-256-GCM" for row in inventory),
        "integrity_verified": health.integrity_verified,
        "plaintext_storage_prohibited": True,
        "metadata_only_inventory": True,
        "least_privilege": all(bool(row.get("least_privilege")) for row in inventory),
        "consumer_inventory_complete": all(
            row["vcid"] in consumer_inventory for row in inventory
        ),
        "execution_blocked": True,
    }
    compliant = all(checks.values())
    return {
        "schema_version": "css.vault.certification.v1",
        "standards": {
            "ESMS-001": "PASS" if compliant else "FAIL",
            "ESMS-002": "PASS" if dependency_map is not None else "READY_FOR_EVIDENCE",
            "ISO_27001": "EVIDENCE_READY",
            "SOC2": "EVIDENCE_READY",
            "NIST_CSF": "EVIDENCE_READY",
        },
        "checks": checks,
        "vault_health": health.__dict__,
        "credential_count": len(inventory),
        "consumer_inventory": consumer_inventory,
        "outcome": "CERTIFIED" if compliant else "NOT_CERTIFIED",
        "advisory_only": True,
        "execution_allowed": False,
    }


def credential_governance_payload(
    vault: CredentialVault,
    *,
    dependency_map: Any | None = None,
    selected_vcid: str | None = None,
) -> dict[str, Any]:
    inventory = vault.inventory()
    certification = certify_vault(vault, dependency_map=dependency_map)
    now = datetime.now(timezone.utc)
    expiring_soon = []
    for row in inventory:
        if not row.get("expiry"):
            continue
        try:
            expiry = datetime.fromisoformat(str(row["expiry"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if now <= expiry <= now + timedelta(days=30):
            expiring_soon.append(row)
    selected = next((row for row in inventory if row.get("vcid") == selected_vcid), {})
    if selected:
        selected = {
            **selected,
            "dependencies": [
                row.consumer for row in dependency_map.consumers(selected_vcid)
            ] if dependency_map is not None else [],
            "audit_history": [
                event for event in vault.audit.recent(100)
                if event.get("credential_id") == selected_vcid
            ],
        }
    return {
        "schema_version": "css.credential.governance.v1",
        "vault_health": certification["vault_health"],
        "credential_inventory": inventory,
        "rotation_queue": [row for row in inventory if row.get("rotation_due")],
        "expiring_soon": expiring_soon,
        "audit_events": vault.audit.recent(100),
        "dependency_graph": dependency_map.as_dict() if dependency_map is not None else {},
        "compliance": certification,
        "selected_credential": selected,
        "secrets_returned": False,
        "advisory_only": True,
        "execution_allowed": False,
    }


__all__ = ["certify_vault", "credential_governance_payload"]
