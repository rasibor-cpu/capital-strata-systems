"""Phase 187A-R1 — immutable provider fingerprint."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from backend.app.market.oanda_readonly_certification.contracts import (
    PROVIDER_NAME,
    PROVIDER_VERSION,
    SCHEMA_VERSION,
)

ADAPTER_VERSION = "187A.2"
DEFAULT_API_VERSION = "v3"


@dataclass(frozen=True)
class ProviderFingerprint:
    provider_name: str = PROVIDER_NAME
    provider_version: str = PROVIDER_VERSION
    adapter_version: str = ADAPTER_VERSION
    endpoint: str = ""
    api_version: str = DEFAULT_API_VERSION
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}

    def fingerprint_hash(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def differs_from(self, other: "ProviderFingerprint") -> tuple[str, ...]:
        """Return deterministic invalidation trigger ids for changed fields."""
        triggers: list[str] = []
        if self.provider_version != other.provider_version:
            triggers.append("provider_version_change")
        if self.adapter_version != other.adapter_version:
            triggers.append("adapter_version_change")
        if self.endpoint != other.endpoint:
            triggers.append("endpoint_change")
        if self.api_version != other.api_version:
            triggers.append("api_version_change")
        if self.schema_version != other.schema_version:
            triggers.append("schema_version_change")
        if self.provider_name != other.provider_name:
            triggers.append("provider_version_change")
        return tuple(triggers)


def build_provider_fingerprint(
    *,
    endpoint: str = "",
    api_version: str = DEFAULT_API_VERSION,
    provider_name: str = PROVIDER_NAME,
    provider_version: str = PROVIDER_VERSION,
    adapter_version: str = ADAPTER_VERSION,
    schema_version: str = SCHEMA_VERSION,
) -> ProviderFingerprint:
    return ProviderFingerprint(
        provider_name=provider_name,
        provider_version=provider_version,
        adapter_version=adapter_version,
        endpoint=endpoint,
        api_version=api_version,
        schema_version=schema_version,
    )
