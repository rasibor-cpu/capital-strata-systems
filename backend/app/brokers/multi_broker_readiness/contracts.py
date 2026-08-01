"""Phase 189 — broker-agnostic certification contracts with capability profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

FRAMEWORK_VERSION = "189.1"
SCHEMA_VERSION = "189.1"
PROVIDER_NAME = "MULTI_BROKER_OPERATIONAL_READINESS_FRAMEWORK"


class BrokerType(str, Enum):
    """Broker identity (plugin-extensible)."""

    OANDA = "OANDA"
    IBKR = "IBKR"
    COINBASE = "COINBASE"
    BINANCE = "BINANCE"
    QUESTRADE = "QUESTRADE"
    PLUGIN = "PLUGIN"


class AssetClass(str, Enum):
    """Asset classes for broker+asset certification scope."""

    EQUITIES = "EQUITIES"
    ETFS = "ETFS"
    FX = "FX"
    CRYPTO = "CRYPTO"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    CFDS = "CFDS"
    INDICES = "INDICES"
    COMMODITIES = "COMMODITIES"
    MULTI = "MULTI"
    NONE = "NONE"


@dataclass(frozen=True)
class BrokerCapabilityProfile:
    """Immutable declared capabilities. Nothing is inferred — callers must declare."""

    schema_id: str = "BROKER_CAPABILITY_PROFILE"
    schema_version: str = SCHEMA_VERSION
    broker_type: str = ""
    # Asset classes
    equities: bool = False
    etfs: bool = False
    fx: bool = False
    crypto: bool = False
    futures: bool = False
    options: bool = False
    cfds: bool = False
    indices: bool = False
    commodities: bool = False
    # Operational capabilities
    account_information: bool = False
    market_data: bool = False
    historical_data: bool = False
    streaming_quotes: bool = False
    paper_trading: bool = False
    live_trading: bool = False  # declared support only — never grants authority
    margin: bool = False
    short_selling: bool = False
    options_chains: bool = False
    fractional_trading: bool = False
    corporate_actions: bool = False
    # Phase 189 safety: live_trading declaration never implies execution_authority
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_authority"] = False
        return payload

    def supported_asset_classes(self) -> tuple[str, ...]:
        mapping = {
            AssetClass.EQUITIES.value: self.equities,
            AssetClass.ETFS.value: self.etfs,
            AssetClass.FX.value: self.fx,
            AssetClass.CRYPTO.value: self.crypto,
            AssetClass.FUTURES.value: self.futures,
            AssetClass.OPTIONS.value: self.options,
            AssetClass.CFDS.value: self.cfds,
            AssetClass.INDICES.value: self.indices,
            AssetClass.COMMODITIES.value: self.commodities,
        }
        return tuple(k for k, v in mapping.items() if v)

    def supports_asset_class(self, asset_class: AssetClass | str) -> bool:
        key = asset_class.value if isinstance(asset_class, AssetClass) else str(asset_class).upper()
        if key == AssetClass.MULTI.value:
            return bool(self.supported_asset_classes())
        if key == AssetClass.NONE.value:
            return True
        return key in self.supported_asset_classes()

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("BrokerCapabilityProfile must not grant execution_authority")


@dataclass(frozen=True)
class BrokerProviderFingerprint:
    broker_type: str
    asset_class: str = AssetClass.NONE.value
    provider_name: str = PROVIDER_NAME
    provider_version: str = FRAMEWORK_VERSION
    adapter_version: str = ""
    endpoint: str = ""
    api_version: str = ""
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}

    def fingerprint_hash(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class BrokerCertificationGeneration:
    certification_id: str = ""
    certification_generation: int = 0
    certification_timestamp: str = ""
    schema_id: str = "BROKER_CERTIFICATION_GENERATION"
    schema_version: str = SCHEMA_VERSION
    broker_type: str = ""
    asset_class: str = AssetClass.NONE.value
    provider_version: str = FRAMEWORK_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __post_init__(self) -> None:
        if self.certification_generation < 0:
            raise ValueError("certification_generation must be >= 0")


@dataclass(frozen=True)
class BrokerOperationalReadiness:
    schema_id: str = "BROKER_OPERATIONAL_READINESS"
    schema_version: str = SCHEMA_VERSION
    broker_type: str = ""
    asset_class: str = AssetClass.NONE.value
    timestamp: str = ""
    readiness_state: str = "NOT_STARTED"
    classification: str = "NOT_STARTED"
    credentials_present: bool = False
    endpoint_valid: bool = False
    environment_valid: bool = False
    configuration_complete: bool = False
    provider_compatible: bool = False
    schema_compatible: bool = False
    capability_compatible: bool = False
    market_data_capable: bool = False
    account_capable: bool = False
    execution_capable: bool = False
    paper_supported: bool = False
    live_read_only_supported: bool = False
    certification_ready: bool = False
    evidence_ready: bool = False
    remaining_blockers: tuple[str, ...] = ()
    capability_profile: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_authority"] = False
        payload["remaining_blockers"] = list(self.remaining_blockers)
        return payload

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("BrokerOperationalReadiness must not grant execution_authority")


@dataclass(frozen=True)
class BrokerCertificationEvidence:
    schema_id: str = "BROKER_CERTIFICATION_EVIDENCE"
    schema_version: str = SCHEMA_VERSION
    broker_type: str = ""
    asset_class: str = AssetClass.NONE.value
    timestamp: str = ""
    certification_state: str = "NOT_STARTED"
    provider_fingerprint_hash: str = ""
    capability_profile: Mapping[str, Any] = field(default_factory=dict)
    operational_readiness: Mapping[str, Any] = field(default_factory=dict)
    remaining_blockers: tuple[str, ...] = ()
    ttl_status: Mapping[str, Any] = field(default_factory=dict)
    rc004_readiness: Mapping[str, Any] = field(default_factory=dict)
    provider_versions: Mapping[str, str] = field(default_factory=dict)
    schema_versions: Mapping[str, str] = field(default_factory=dict)
    gate_results: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    parent_certification_id: str = ""
    previous_evidence_hash: str = ""
    current_evidence_hash: str = ""
    lineage_generation: int = 0
    evidence_hash: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["remaining_blockers"] = list(self.remaining_blockers)
        payload["gate_results"] = list(self.gate_results)
        return payload


@dataclass(frozen=True)
class BrokerReadOnlyCertification:
    schema_id: str = "BROKER_READONLY_CERTIFICATION"
    schema_version: str = SCHEMA_VERSION
    provider_name: str = PROVIDER_NAME
    provider_version: str = FRAMEWORK_VERSION
    broker_type: str = ""
    asset_class: str = AssetClass.NONE.value
    timestamp: str = ""
    certification_state: str = "NOT_STARTED"
    failure_reason: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    certification_id: str = ""
    certification_generation: int = 0
    certification_timestamp: str = ""
    provider_fingerprint_hash: str = ""
    parent_certification_id: str = ""
    evidence_hash: str = ""
    capability_profile: Mapping[str, Any] = field(default_factory=dict)
    operational_readiness: BrokerOperationalReadiness | None = None
    ttl_status: Mapping[str, Any] = field(default_factory=dict)
    rc004_readiness: Mapping[str, Any] = field(default_factory=dict)
    remaining_blockers: tuple[str, ...] = ()
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_authority"] = False
        payload["remaining_blockers"] = list(self.remaining_blockers)
        return payload

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("BrokerReadOnlyCertification must not grant execution_authority")
        if self.certification_generation < 0:
            raise ValueError("certification_generation must be >= 0")
