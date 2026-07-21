"""Opaque vault handles and canonical VCID generation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import secrets
import threading


def _code(value: str, length: int) -> str:
    cleaned = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    return (cleaned[:length] or "X").ljust(length, "X")


def _broker_code(value: str) -> str:
    canonical = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    registered = {"QUESTRADE": "QT", "COINBASE": "CB", "BINANCE": "BN", "OANDA": "OA"}
    return registered.get(canonical, _code(canonical, 2))


class VCIDGenerator:
    def __init__(self, start: int = 0):
        self._counter = int(start)
        self._lock = threading.Lock()

    def issue(self, broker: str, credential_type: str) -> str:
        with self._lock:
            self._counter += 1
            serial = self._counter
        return f"VCID-BRK-{_broker_code(broker)}-{serial:06d}"


@dataclass(frozen=True)
class VaultHandle:
    vcid: str
    fingerprint: str
    capability: str
    issued_to: str
    nonce: str

    def __repr__(self) -> str:
        return (
            f"VaultHandle(vcid={self.vcid!r}, fingerprint={self.fingerprint!r}, "
            f"capability={self.capability!r}, issued_to={self.issued_to!r})"
        )


def issue_handle(*, vcid: str, fingerprint: str, capability: str, consumer: str) -> VaultHandle:
    return VaultHandle(
        vcid=vcid,
        fingerprint=fingerprint,
        capability=str(capability).upper(),
        issued_to=str(consumer),
        nonce=hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:24],
    )


__all__ = ["VCIDGenerator", "VaultHandle", "issue_handle"]
