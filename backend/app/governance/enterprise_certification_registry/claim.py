"""Phase 191 — runtime rule: no certification claim without valid registry entry."""

from __future__ import annotations

from backend.app.governance.enterprise_certification_registry.models import CertificationRegistryEntry
from backend.app.governance.enterprise_certification_registry.query import RegistryQuery
from backend.app.governance.enterprise_certification_registry.repository import RegistryRepository


class CertificationClaimError(PermissionError):
    """Raised when a certification claim is invalid or unauthorized."""


def assert_valid_certification_claim(
    repository: RegistryRepository,
    *,
    registry_id: str,
    required_status: str | None = None,
    allow_suspended: bool = False,
) -> CertificationRegistryEntry:
    """Nothing may claim certification without a valid ACTIVE registry entry.

    Execution remains disabled: even a valid entry never grants execution_authority.
    """
    entry = repository.get(registry_id)
    if entry is None:
        raise CertificationClaimError(f"no_registry_entry:{registry_id}")
    if entry.execution_authority:
        raise CertificationClaimError("execution_authority_forbidden")
    if entry.suspension_status != "ACTIVE" and not allow_suspended:
        raise CertificationClaimError(f"entry_not_active:{entry.suspension_status}")
    if entry.live_status not in {"NOT_AUTHORIZED", "BLOCKED", "SUSPENDED", "NOT_STARTED"}:
        raise CertificationClaimError(f"invalid_live_status_claim:{entry.live_status}")
    if required_status and entry.certification_status != required_status:
        raise CertificationClaimError(
            f"status_mismatch:expected={required_status}:actual={entry.certification_status}"
        )
    # Dual-check via query surface for certified RO claims.
    if required_status == "READ_ONLY_CERTIFIED":
        query = RegistryQuery(repository)
        ids = {e.registry_id for e in query.certified_readonly()}
        if registry_id not in ids and entry.read_only_status not in {"CERTIFIED", "FRAMEWORK_READY"}:
            raise CertificationClaimError("read_only_claim_not_in_certified_set")
    return entry
