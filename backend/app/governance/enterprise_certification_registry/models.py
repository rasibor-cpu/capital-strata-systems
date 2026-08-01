"""Phase 191 — immutable certification registry entity model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

FRAMEWORK_VERSION = "191.1"
SCHEMA_VERSION = "191.1"
REGISTRY_NAME = "ENTERPRISE_CERTIFICATION_REGISTRY"


class RegistryEntityType(str, Enum):
    BROKER = "BROKER"
    PROVIDER = "PROVIDER"
    ASSET = "ASSET"
    MARKET_DATA = "MARKET_DATA"
    FX = "FX"
    MICROSTRUCTURE = "MICROSTRUCTURE"
    PLUGIN = "PLUGIN"
    GOVERNANCE = "GOVERNANCE"
    PHASE = "PHASE"
    # Extensible: new types may be registered as string values via PLUGIN/custom entries.


@dataclass(frozen=True)
class CertificationRegistryEntry:
    """Immutable registry entry. Nothing is inferred — all fields must be declared."""

    registry_id: str
    entity_type: str
    entity_name: str
    broker_type: str = ""
    asset_class: str = ""
    provider_name: str = ""
    provider_version: str = ""
    schema_version: str = SCHEMA_VERSION
    capability_profile: Mapping[str, Any] = field(default_factory=dict)
    certification_status: str = "NOT_STARTED"
    operational_readiness: str = "NOT_STARTED"
    paper_status: str = "NOT_STARTED"
    read_only_status: str = "NOT_STARTED"
    live_status: str = "NOT_AUTHORIZED"
    execution_authority: bool = False
    authorization_ttl_status: str = "NONE"
    certification_generation: int = 0
    evidence_hash: str = ""
    last_validation: str = ""
    next_validation: str = ""
    suspension_status: str = "ACTIVE"
    blocker_list: tuple[str, ...] = ()
    phase_refs: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_authority"] = False
        payload["blocker_list"] = list(self.blocker_list)
        payload["phase_refs"] = list(self.phase_refs)
        return payload

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("CertificationRegistryEntry must not grant execution_authority")
        if not self.registry_id:
            raise ValueError("registry_id required")
        if not self.entity_type:
            raise ValueError("entity_type required")
        if not self.entity_name:
            raise ValueError("entity_name required")
        if self.certification_generation < 0:
            raise ValueError("certification_generation must be >= 0")
        if self.suspension_status not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
            raise ValueError(f"invalid suspension_status: {self.suspension_status}")
