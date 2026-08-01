"""Phase 187A / 187A-R1 — immutable OANDA read-only certification contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional

FRAMEWORK_VERSION = "187A.2"
SCHEMA_VERSION = "187A.2"
PROVIDER_NAME = "OANDA_ONLINE_READONLY_CERTIFICATION_FRAMEWORK"
PROVIDER_VERSION = "187A.2"

SCHEMA_CONNECTION = "OANDA_CONNECTION_STATUS"
SCHEMA_AUTHENTICATION = "OANDA_AUTHENTICATION_STATUS"
SCHEMA_ACCOUNT = "OANDA_ACCOUNT_STATUS"
SCHEMA_MARKETDATA = "OANDA_MARKETDATA_STATUS"
SCHEMA_CERTIFICATION = "OANDA_READONLY_CERTIFICATION"


@dataclass(frozen=True)
class OandaConnectionStatus:
    schema_id: str = SCHEMA_CONNECTION
    schema_version: str = SCHEMA_VERSION
    provider_name: str = PROVIDER_NAME
    provider_version: str = PROVIDER_VERSION
    timestamp: str = ""
    certification_state: str = "NOT_STARTED"
    failure_reason: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    certification_id: str = ""
    certification_generation: int = 0
    certification_timestamp: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OandaAuthenticationStatus:
    schema_id: str = SCHEMA_AUTHENTICATION
    schema_version: str = SCHEMA_VERSION
    provider_name: str = PROVIDER_NAME
    provider_version: str = PROVIDER_VERSION
    timestamp: str = ""
    certification_state: str = "NOT_STARTED"
    failure_reason: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    certification_id: str = ""
    certification_generation: int = 0
    certification_timestamp: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OandaAccountStatus:
    schema_id: str = SCHEMA_ACCOUNT
    schema_version: str = SCHEMA_VERSION
    provider_name: str = PROVIDER_NAME
    provider_version: str = PROVIDER_VERSION
    timestamp: str = ""
    certification_state: str = "NOT_STARTED"
    failure_reason: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    certification_id: str = ""
    certification_generation: int = 0
    certification_timestamp: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OandaMarketDataStatus:
    schema_id: str = SCHEMA_MARKETDATA
    schema_version: str = SCHEMA_VERSION
    provider_name: str = PROVIDER_NAME
    provider_version: str = PROVIDER_VERSION
    timestamp: str = ""
    certification_state: str = "NOT_STARTED"
    failure_reason: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    certification_id: str = ""
    certification_generation: int = 0
    certification_timestamp: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OandaReadOnlyCertification:
    """Aggregate read-only certification result. Never grants execution authority."""

    schema_id: str = SCHEMA_CERTIFICATION
    schema_version: str = SCHEMA_VERSION
    provider_name: str = PROVIDER_NAME
    provider_version: str = PROVIDER_VERSION
    timestamp: str = ""
    certification_state: str = "NOT_STARTED"
    failure_reason: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    connection: Optional[OandaConnectionStatus] = None
    authentication: Optional[OandaAuthenticationStatus] = None
    account: Optional[OandaAccountStatus] = None
    market_data: Optional[OandaMarketDataStatus] = None
    evidence_hash: str = ""
    execution_authority: bool = False  # always False in Phase 187A
    certification_id: str = ""
    certification_generation: int = 0
    certification_timestamp: str = ""
    provider_fingerprint_hash: str = ""
    parent_certification_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_authority"] = False
        return payload

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("OandaReadOnlyCertification must not grant execution_authority")
        if self.certification_generation < 0:
            raise ValueError("certification_generation must be >= 0")
