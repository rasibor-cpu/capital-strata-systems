"""AES-256-GCM envelope encryption without persisted plaintext keys."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class VaultIntegrityError(RuntimeError):
    pass


class EncryptionKeyProvider(Protocol):
    def key_bytes(self) -> bytes: ...


@dataclass(frozen=True)
class StaticKeyProvider:
    """Injection helper for tests or an external KMS/OS-secret-store bridge."""

    key: bytes

    def key_bytes(self) -> bytes:
        return bytes(self.key)

    def __repr__(self) -> str:
        return "StaticKeyProvider(key=[REDACTED])"


@dataclass(frozen=True)
class EncryptedPayload:
    nonce_b64: str
    ciphertext_b64: str
    aad_sha256: str
    record_sha256: str


class VaultCrypto:
    algorithm = "AES-256-GCM"

    def __init__(self, key_provider: EncryptionKeyProvider):
        key = key_provider.key_bytes()
        if len(key) != 32:
            raise ValueError("AES_256_KEY_REQUIRED")
        self._key_provider = key_provider

    @staticmethod
    def generate_key() -> bytes:
        return AESGCM.generate_key(bit_length=256)

    def encrypt(self, plaintext: bytes | bytearray | memoryview, *, aad: bytes) -> EncryptedPayload:
        source = bytes(plaintext)
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._key_provider.key_bytes()).encrypt(nonce, source, aad)
        aad_hash = hashlib.sha256(aad).hexdigest()
        record_hash = hashlib.sha256(nonce + ciphertext + aad_hash.encode("ascii")).hexdigest()
        return EncryptedPayload(
            nonce_b64=base64.b64encode(nonce).decode("ascii"),
            ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
            aad_sha256=aad_hash,
            record_sha256=record_hash,
        )

    def fingerprint(self, plaintext: bytes | bytearray | memoryview) -> str:
        digest = hmac.new(self._key_provider.key_bytes(), bytes(plaintext), hashlib.sha256).hexdigest()
        return f"HMAC-SHA256:{digest[:24]}"

    def decrypt(self, payload: EncryptedPayload, *, aad: bytes) -> bytearray:
        try:
            nonce = base64.b64decode(payload.nonce_b64, validate=True)
            ciphertext = base64.b64decode(payload.ciphertext_b64, validate=True)
        except Exception as exc:
            raise VaultIntegrityError("VAULT_RECORD_ENCODING_INVALID") from exc
        expected_aad = hashlib.sha256(aad).hexdigest()
        expected_record = hashlib.sha256(nonce + ciphertext + expected_aad.encode("ascii")).hexdigest()
        if expected_aad != payload.aad_sha256 or expected_record != payload.record_sha256:
            raise VaultIntegrityError("VAULT_RECORD_INTEGRITY_FAILED")
        try:
            return bytearray(AESGCM(self._key_provider.key_bytes()).decrypt(nonce, ciphertext, aad))
        except InvalidTag as exc:
            raise VaultIntegrityError("VAULT_RECORD_AUTHENTICATION_FAILED") from exc

    @staticmethod
    def canonical_aad(metadata: dict) -> bytes:
        safe = {
            key: metadata.get(key)
            for key in ("vcid", "broker", "credential_type", "classification", "created", "version")
        }
        return json.dumps(safe, sort_keys=True, separators=(",", ":")).encode("utf-8")


def zeroize(value: bytearray | memoryview) -> None:
    target = value if isinstance(value, memoryview) else memoryview(value)
    if target.readonly:
        return
    target[:] = b"\x00" * len(target)


__all__ = [
    "EncryptedPayload",
    "EncryptionKeyProvider",
    "StaticKeyProvider",
    "VaultCrypto",
    "VaultIntegrityError",
    "zeroize",
]
