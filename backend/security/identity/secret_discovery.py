"""Enterprise-only discovery path for credential-bearing configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Mapping

from backend.security.identity.enterprise_secret_service import (
    DuplicateSecretError,
    EnterpriseSecretService,
)

_SECRET_NAME = re.compile(
    r"(API_KEY|API_SECRET|OAUTH_TOKEN|ACCESS_TOKEN|REFRESH_TOKEN|CERTIFICATE|"
    r"PASSWORD|PRIVATE_KEY|CLIENT_SECRET|BROKER_SECRET)$",
    re.I,
)


@dataclass(frozen=True)
class DiscoveryResult:
    source_key: str
    registered: bool
    duplicate: bool
    secret_uuid: str | None
    handle_reference: str | None
    reason: str


class EnterpriseSecretDiscovery:
    def __init__(self, service: EnterpriseSecretService, *, approved_sources: set[str] | None = None):
        self.service = service
        self.approved_sources = approved_sources or {"environment", "profile", "operator_import"}

    def register_mapping(
        self,
        source: str,
        values: Mapping[str, str],
        *,
        provider: str,
        owner: str,
        environment: str,
        operator: str,
    ) -> dict:
        if source not in self.approved_sources:
            raise PermissionError("SECRET_DISCOVERY_SOURCE_NOT_APPROVED")
        results = []
        for key, raw in values.items():
            if not _SECRET_NAME.search(str(key)) or not str(raw):
                continue
            material = bytearray(str(raw).encode("utf-8"))
            try:
                metadata = self.service.register(
                    material,
                    provider=provider,
                    secret_type=str(key),
                    owner=owner,
                    environment=environment,
                    operator=operator,
                    broker=_broker_from_key(str(key)),
                )
                result = DiscoveryResult(
                    source_key=str(key),
                    registered=True,
                    duplicate=False,
                    secret_uuid=metadata.secret_uuid,
                    handle_reference=f"secret-handle:{metadata.secret_uuid}",
                    reason="REGISTERED",
                )
            except DuplicateSecretError as exc:
                result = DiscoveryResult(
                    source_key=str(key),
                    registered=False,
                    duplicate=True,
                    secret_uuid=None,
                    handle_reference=None,
                    reason=str(exc).split(":", 1)[0],
                )
            finally:
                material[:] = b"\x00" * len(material)
            results.append(result)
        return {
            "schema_version": "css.enterprise_secret.discovery.v1",
            "source": source,
            "results": [asdict(row) for row in results],
            "plaintext_returned": False,
            "source_values_deleted": False,
            "execution_allowed": False,
        }


def _broker_from_key(key: str) -> str | None:
    prefix = str(key).split("_", 1)[0].upper()
    return prefix if prefix in {"COINBASE", "BINANCE", "OANDA", "QUESTRADE"} else None


__all__ = ["DiscoveryResult", "EnterpriseSecretDiscovery"]
