"""Pinned paper-issuer registry. Fail-closed when no issuer is enrolled.

A test or simulation registers issuer keys explicitly via ``register_issuer``.
The registry never generates keys, never reads a runtime key file, and never
persists anywhere. An issuer is a *paper simulation* authority only; it is not
a production release signer and never grants execution authority.

This registry is additive scaffolding for paper-authority simulation tests and
does not touch ``config/governance/pilot_approver_enrollment.json`` (production
sponsor/reviewer enrollment) or any execution flag.
"""
from __future__ import annotations

import logging
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

log = logging.getLogger(__name__)


class PaperIssuerRegistryError(RuntimeError):
    """Raised when the registry cannot serve a trusted issuer."""


class PaperIssuerRegistry:
    """In-memory pinned paper-issuer registry. Fail-closed on missing entry."""

    def __init__(self) -> None:
        self._keys: dict[str, Ed25519PublicKey] = {}

    def register_issuer(
        self,
        *,
        issuer_id: str,
        public_key: Ed25519PublicKey,
    ) -> None:
        """Explicitly register one issuer. Test/simulation callers only."""
        if type(issuer_id) is not str or not issuer_id.strip():
            raise PaperIssuerRegistryError("issuer_id required")
        if not isinstance(public_key, Ed25519PublicKey):
            raise PaperIssuerRegistryError("Ed25519PublicKey required")
        if issuer_id in self._keys:
            log.warning("PaperIssuerRegistry replacing issuer id=%s", issuer_id)
        self._keys[issuer_id] = public_key
        log.info("PaperIssuerRegistry registered issuer id=%s", issuer_id)

    def issuer_public_key(self, issuer_id: str) -> Ed25519PublicKey:
        """Return the pinned public key, or raise (fail closed)."""
        if type(issuer_id) is not str or not issuer_id.strip():
            raise PaperIssuerRegistryError("issuer_id required")
        key = self._keys.get(issuer_id)
        if key is None:
            log.warning("PaperIssuerRegistry lookup failed issuer_id=%s", issuer_id)
            raise PaperIssuerRegistryError(f"issuer_not_enrolled:{issuer_id}")
        return key

    def is_enrolled(self, issuer_id: str) -> bool:
        """True only if a key is explicitly registered for issuer_id."""
        return type(issuer_id) is str and issuer_id in self._keys

    def enrolled_issuer_ids(self) -> tuple[str, ...]:
        return tuple(self._keys.keys())

    def clear(self) -> None:
        """Remove all issuer entries. Used by test teardown only."""
        self._keys.clear()
        log.info("PaperIssuerRegistry cleared")


_default_registry: Optional[PaperIssuerRegistry] = None


def default_paper_issuer_registry() -> PaperIssuerRegistry:
    """Return a lazily constructed shared registry. Empty by default (fail closed)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = PaperIssuerRegistry()
    return _default_registry
