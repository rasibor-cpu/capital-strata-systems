"""Phase 191 — registry validator (immutable rules)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.app.governance.enterprise_certification_registry.models import (
    SCHEMA_VERSION,
    CertificationRegistryEntry,
    RegistryEntityType,
)

KNOWN_ENTITY_TYPES = {e.value for e in RegistryEntityType}

VALID_CERT_STATUS = {
    "NOT_STARTED",
    "PARTIAL",
    "FRAMEWORK_READY",
    "READ_ONLY_CERTIFIED",
    "PAPER_ONLY",
    "BLOCKED",
    "SUSPENDED",
    "REVOKED",
}

VALID_READINESS = {"NOT_STARTED", "PARTIAL", "READY", "BLOCKED", "UNKNOWN"}
VALID_PAPER = {"NOT_STARTED", "ACKNOWLEDGED", "CERTIFIED", "BLOCKED", "N/A"}
VALID_RO = {"NOT_STARTED", "FRAMEWORK_READY", "CERTIFIED", "PARTIAL", "BLOCKED", "N/A"}
VALID_LIVE = {"NOT_AUTHORIZED", "NOT_STARTED", "BLOCKED", "SUSPENDED"}
VALID_TTL = {"NONE", "ACTIVE", "EXPIRED", "N/A"}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "errors": list(self.errors)}


class RegistryValidator:
    """Validates registry entries without mutating them."""

    def validate_entry(self, entry: CertificationRegistryEntry) -> ValidationResult:
        errors: list[str] = []
        if entry.execution_authority:
            errors.append("execution_authority_must_be_false")
        if entry.entity_type not in KNOWN_ENTITY_TYPES and entry.entity_type != "CUSTOM":
            # Extensible: CUSTOM allowed for future types without enum change.
            if not entry.entity_type.isupper() or " " in entry.entity_type:
                errors.append(f"invalid_entity_type:{entry.entity_type}")
        if entry.certification_status not in VALID_CERT_STATUS:
            errors.append(f"invalid_certification_status:{entry.certification_status}")
        if entry.operational_readiness not in VALID_READINESS:
            errors.append(f"invalid_operational_readiness:{entry.operational_readiness}")
        if entry.paper_status not in VALID_PAPER:
            errors.append(f"invalid_paper_status:{entry.paper_status}")
        if entry.read_only_status not in VALID_RO:
            errors.append(f"invalid_read_only_status:{entry.read_only_status}")
        if entry.live_status not in VALID_LIVE:
            errors.append(f"invalid_live_status:{entry.live_status}")
        if entry.authorization_ttl_status not in VALID_TTL:
            errors.append(f"invalid_authorization_ttl_status:{entry.authorization_ttl_status}")
        if entry.live_status not in {"NOT_AUTHORIZED", "BLOCKED", "SUSPENDED", "NOT_STARTED"}:
            errors.append("live_status_must_remain_non_authorized")
        if entry.certification_status in {"READ_ONLY_CERTIFIED", "FRAMEWORK_READY"} and not entry.schema_version:
            errors.append("schema_version_required_for_certified")
        if entry.schema_version and not (
            entry.schema_version.startswith("187")
            or entry.schema_version.startswith("188")
            or entry.schema_version.startswith("189")
            or entry.schema_version.startswith("190")
            or entry.schema_version.startswith("191")
            or entry.schema_version == SCHEMA_VERSION
        ):
            # Allow declared historical schema versions from prior phases.
            if not any(ch.isdigit() for ch in entry.schema_version):
                errors.append(f"invalid_schema_version:{entry.schema_version}")
        # Certified claims require evidence hash for RO certified status.
        if entry.certification_status == "READ_ONLY_CERTIFIED" and not entry.evidence_hash:
            errors.append("evidence_hash_required_for_read_only_certified")
        if entry.suspension_status == "SUSPENDED" and entry.certification_status not in {
            "SUSPENDED",
            "BLOCKED",
            "REVOKED",
            "PARTIAL",
            "NOT_STARTED",
            "FRAMEWORK_READY",
            "PAPER_ONLY",
            "READ_ONLY_CERTIFIED",
        }:
            errors.append("suspended_entry_status_incoherent")
        return ValidationResult(ok=not errors, errors=tuple(errors))

    def validate_many(self, entries: Sequence[CertificationRegistryEntry]) -> ValidationResult:
        errors: list[str] = []
        seen: set[str] = set()
        for entry in entries:
            if entry.registry_id in seen:
                errors.append(f"duplicate_registry_id:{entry.registry_id}")
            seen.add(entry.registry_id)
            result = self.validate_entry(entry)
            for err in result.errors:
                errors.append(f"{entry.registry_id}:{err}")
        return ValidationResult(ok=not errors, errors=tuple(errors))
