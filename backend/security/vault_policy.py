"""Least-privilege policy for vault metadata and runtime leases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from backend.security.vault_handles import VaultHandle


@dataclass(frozen=True)
class VaultAccessDecision:
    allowed: bool
    reason_code: str


class VaultPolicy:
    def __init__(self, trusted_consumers: Mapping[str, set[str]] | None = None):
        self._trusted = {
            str(vcid): {str(consumer) for consumer in consumers}
            for vcid, consumers in (trusted_consumers or {}).items()
        }

    def authorize_consumer(self, vcid: str, consumer: str) -> None:
        self._trusted.setdefault(str(vcid), set()).add(str(consumer))

    def revoke_consumer(self, vcid: str, consumer: str) -> None:
        self._trusted.get(str(vcid), set()).discard(str(consumer))

    def runtime_lease(self, handle: VaultHandle, *, consumer: str) -> VaultAccessDecision:
        if handle.capability != "RUNTIME_USE":
            return VaultAccessDecision(False, "HANDLE_CAPABILITY_DENIED")
        if handle.issued_to != str(consumer):
            return VaultAccessDecision(False, "HANDLE_CONSUMER_MISMATCH")
        if str(consumer) not in self._trusted.get(handle.vcid, set()):
            return VaultAccessDecision(False, "CONSUMER_NOT_AUTHORIZED")
        return VaultAccessDecision(True, "AUTHORIZED")

    def consumer_inventory(self, vcid: str) -> tuple[str, ...]:
        return tuple(sorted(self._trusted.get(str(vcid), set())))


__all__ = ["VaultAccessDecision", "VaultPolicy"]
