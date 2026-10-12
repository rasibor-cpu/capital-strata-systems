"""Paper-only authorization verifier. No issuer, keys, or live wiring.

A valid signature is necessary but never sufficient for an order: independently
verified RiskGovernor/R7/AntiBleed/kill-switch decisions and atomic nonce claims
are still required. This module does not submit or reserve orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_FIELDS = frozenset({"mode", "candidate_sha", "broker", "account", "instrument", "parent_id",
                     "child_id", "side", "quantity", "limit_price", "quote_currency",
                     "risk_currency", "risk_amount", "issued_at", "expires_at", "nonce",
                     "r7", "antibleed", "risk_governor", "kill_switch_clear"})
_REQUIRED_TRUE = ("r7", "antibleed", "risk_governor", "kill_switch_clear")


def canonical_paper_intent_digest(payload: dict[str, Any]) -> bytes:
    """Strict canonical digest; caller must supply a complete exact-field payload."""
    if type(payload) is not dict or set(payload) != _FIELDS:
        raise ValueError("missing or unknown signed fields")
    if payload["mode"] != "PAPER":
        raise ValueError("paper-only authorization")
    for name in ("candidate_sha", "broker", "account", "instrument", "parent_id",
                 "child_id", "side", "quote_currency", "risk_currency", "nonce"):
        if type(payload[name]) is not str or not payload[name].strip():
            raise ValueError("invalid intent identifier")
    if len(payload["candidate_sha"]) != 40 or any(c not in "0123456789abcdef" for c in payload["candidate_sha"]):
        raise ValueError("invalid candidate SHA")
    if payload["side"] not in ("BUY", "SELL"):
        raise ValueError("invalid side")
    for name in ("quantity", "limit_price", "risk_amount"):
        value = payload[name]
        if type(value) is not str:
            raise ValueError("canonical decimal must be string")
        try:
            amount = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("invalid amount") from exc
        if not amount.is_finite() or amount <= 0 or str(amount) != value:
            raise ValueError("invalid canonical amount")
    if any(payload[k] is not True for k in _REQUIRED_TRUE):
        raise ValueError("independent risk gates must all pass")
    for key in ("issued_at", "expires_at"):
        if type(payload[key]) is not str:
            raise ValueError("timestamp must be ISO text")
        parsed = datetime.fromisoformat(payload[key])
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).digest()


@dataclass(frozen=True)
class PaperAuthorizationVerification:
    valid: bool
    reason: str


def verify_paper_intent_signature(
    payload: dict[str, Any],
    signature: bytes,
    public_key: bytes,
    *,
    expected_candidate_sha: str,
    expected_broker: str,
    expected_account: str,
    expected_instrument: str,
    expected_child_id: str,
    now: datetime,
) -> PaperAuthorizationVerification:
    """Check cryptographic binding and expiry; *not* proof of trusted issuer.

    Callers must load public key from a separately authenticated pinned issuer
    registry, verify live kill switch and actual risk gate evidence, and atomically
    consume nonce. Never treat True as execution authority.
    """
    try:
        digest = canonical_paper_intent_digest(payload)
        if type(now) is not datetime or now.tzinfo is None:
            raise ValueError("aware now required")
        for field, value in (("candidate_sha", expected_candidate_sha),
                             ("broker", expected_broker), ("account", expected_account),
                             ("instrument", expected_instrument), ("child_id", expected_child_id)):
            if type(value) is not str or payload[field] != value:
                raise ValueError("intent binding mismatch")
        start = datetime.fromisoformat(payload["issued_at"])
        end = datetime.fromisoformat(payload["expires_at"])
        current = now.astimezone(timezone.utc)
        if not start.astimezone(timezone.utc) <= current < end.astimezone(timezone.utc):
            raise ValueError("intent expired/not yet valid")
        if not timedelta(0) < end - start <= timedelta(seconds=120):
            raise ValueError("intent expiry window too long")
        if type(signature) is not bytes or len(signature) != 64:
            raise ValueError("invalid signature")
        if type(public_key) is not bytes or len(public_key) != 32:
            raise ValueError("invalid public key")
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, digest)
        return PaperAuthorizationVerification(True, "SIGNATURE_AND_BINDING_VERIFIED_ONLY")
    except (ValueError, TypeError, OverflowError, InvalidSignature):
        return PaperAuthorizationVerification(False, "PAPER_INTENT_AUTHORIZATION_REJECTED")
