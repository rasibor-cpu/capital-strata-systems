"""Approved-source credential discovery and non-destructive migration planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Mapping

from backend.security.credential_vault import CredentialVault
from backend.security.vault_models import CredentialClassification

_CREDENTIAL_KEY = re.compile(
    r"(API_KEY|API_SECRET|ACCESS_TOKEN|REFRESH_TOKEN|PRIVATE_KEY|PASSWORD|CLIENT_SECRET|CERTIFICATE)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DiscoveryCandidate:
    source: str
    source_key: str
    broker: str
    credential_type: str
    present: bool
    valid: bool


@dataclass(frozen=True)
class MigrationEntry:
    source: str
    source_key: str
    vcid: str
    runtime_reference: str
    original_retained: bool = True
    plaintext_reported: bool = False


class CredentialDiscovery:
    def __init__(self, approved_sources: set[str] | None = None):
        self.approved_sources = approved_sources or {"environment", "profile", "operator_import"}

    def discover(self, source_name: str, values: Mapping[str, str]) -> list[DiscoveryCandidate]:
        if source_name not in self.approved_sources:
            raise PermissionError("CREDENTIAL_SOURCE_NOT_APPROVED")
        candidates = []
        for key, value in values.items():
            if not _CREDENTIAL_KEY.search(str(key)):
                continue
            broker = str(key).split("_", 1)[0].upper()
            credential_type = str(key)[len(broker) + 1 :].upper()
            candidates.append(
                DiscoveryCandidate(
                    source=source_name,
                    source_key=str(key),
                    broker=broker,
                    credential_type=credential_type,
                    present=bool(value),
                    valid=isinstance(value, str) and bool(value.strip()),
                )
            )
        return candidates

    def migrate(
        self,
        source_name: str,
        values: Mapping[str, str],
        *,
        vault: CredentialVault,
        owner: str,
        operator: str,
    ) -> dict:
        entries: list[MigrationEntry] = []
        for candidate in self.discover(source_name, values):
            if not candidate.valid:
                continue
            material = bytearray(str(values[candidate.source_key]).encode("utf-8"))
            try:
                metadata = vault.register(
                    material,
                    broker=candidate.broker,
                    credential_type=candidate.credential_type,
                    owner=owner,
                    operator=operator,
                    classification=CredentialClassification.RESTRICTED,
                )
            finally:
                material[:] = b"\x00" * len(material)
            entries.append(
                MigrationEntry(
                    source=source_name,
                    source_key=candidate.source_key,
                    vcid=metadata.vcid,
                    runtime_reference=f"vault-handle:{metadata.vcid}",
                )
            )
        return {
            "schema_version": "css.credential.migration.v1",
            "entries": [asdict(entry) for entry in entries],
            "original_sources_deleted": False,
            "plaintext_in_report": False,
            "execution_allowed": False,
        }


__all__ = ["CredentialDiscovery", "DiscoveryCandidate", "MigrationEntry"]
