"""Opaque enterprise SecretHandle; never contains credential material."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import secrets
from typing import Any

from backend.security.identity.identity_models import SecretMetadata


@dataclass(frozen=True)
class SecretHandle:
    handle: str
    secret_uuid: str
    vcid: str
    version: int
    provider: str
    broker: str | None
    classification: str
    fingerprint: str
    hash: str
    issued_to: str
    purpose: str

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "plaintext_returned": False, "execution_allowed": False}

    def __repr__(self) -> str:
        return (
            f"SecretHandle(handle={self.handle!r}, secret_uuid={self.secret_uuid!r}, "
            f"version={self.version}, classification={self.classification!r}, redacted=True)"
        )


def canonical_secret_consumer(value: str) -> str:
    """Return the exact, whitespace-normalized identifier bound to a handle."""
    consumer = str(value or "").strip()
    if not consumer:
        raise ValueError("SECRET_HANDLE_CONSUMER_REQUIRED")
    return consumer


def issue_secret_handle(
    metadata: SecretMetadata,
    *,
    identity_id: str,
    purpose: str,
) -> SecretHandle:
    issued_to = canonical_secret_consumer(identity_id)
    nonce = secrets.token_urlsafe(24)
    digest = hashlib.sha256(
        f"{metadata.secret_uuid}|{metadata.version}|{issued_to}|{purpose}|{nonce}".encode("utf-8")
    ).hexdigest()
    return SecretHandle(
        handle=f"SH-{digest[:32].upper()}",
        secret_uuid=metadata.secret_uuid,
        vcid=metadata.vcid,
        version=metadata.version,
        provider=metadata.provider,
        broker=metadata.broker,
        classification=metadata.classification.value,
        fingerprint=metadata.fingerprint,
        hash=metadata.hash,
        issued_to=issued_to,
        purpose=str(purpose),
    )


__all__ = ["SecretHandle", "canonical_secret_consumer", "issue_secret_handle"]
