"""Phase 191 — Enterprise Certification Registry (authoritative offline registry).

NO RUNTIME ACTIVATION. NO EXECUTION AUTHORITY. NO BROKER AUTHENTICATION.
"""

from __future__ import annotations

from backend.app.governance.enterprise_certification_registry.audit import RegistryAudit
from backend.app.governance.enterprise_certification_registry.claim import (
    CertificationClaimError,
    assert_valid_certification_claim,
)
from backend.app.governance.enterprise_certification_registry.exporter import RegistryExporter
from backend.app.governance.enterprise_certification_registry.hashing import RegistryHash
from backend.app.governance.enterprise_certification_registry.models import (
    FRAMEWORK_VERSION,
    SCHEMA_VERSION,
    CertificationRegistryEntry,
    RegistryEntityType,
)
from backend.app.governance.enterprise_certification_registry.query import RegistryQuery
from backend.app.governance.enterprise_certification_registry.repository import RegistryRepository
from backend.app.governance.enterprise_certification_registry.seed import seed_phase_registry
from backend.app.governance.enterprise_certification_registry.snapshot import RegistrySnapshot
from backend.app.governance.enterprise_certification_registry.validator import RegistryValidator

__all__ = [
    "FRAMEWORK_VERSION",
    "SCHEMA_VERSION",
    "RegistryEntityType",
    "CertificationRegistryEntry",
    "RegistryRepository",
    "RegistryValidator",
    "RegistryQuery",
    "RegistryAudit",
    "RegistrySnapshot",
    "RegistryExporter",
    "RegistryHash",
    "seed_phase_registry",
    "assert_valid_certification_claim",
    "CertificationClaimError",
]
