"""Paper-only authority issuer. No live wiring, no runtime key generation.

A ``PaperAuthorityIssuer`` constructs a signed paper intent **only from internal
trusted gate evaluators** (the caller supplies the evaluator callables, never
booleans). The issuer never accepts caller-provided ``r7``, ``antibleed``,
``risk_governor`` or ``kill_switch_clear`` values.

This module:
- does not place orders;
- does not touch broker state;
- does not enroll production keys;
- does not enable the CAD 20 minimum-size exception;
- does not change any execution_allowed / live_trading_blocked flag.

A signed intent is a *necessary* prerequisite for paper simulation only; it is
never execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import secrets
from typing import Any, Callable, Mapping, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.runtime.pilot_paper_authorization import canonical_paper_intent_digest

log = logging.getLogger(__name__)

INTENT_EXPIRY_SECONDS = 120
_R7_KEY = "r7"
_ANTIBLEED_KEY = "antibleed"
_RISK_GOVERNOR_KEY = "risk_governor"
_KILL_SWITCH_CLEAR_KEY = "kill_switch_clear"
_REQUIRED_TRUE_FIELDS = (_R7_KEY, _ANTIBLEED_KEY, _RISK_GOVERNOR_KEY, _KILL_SWITCH_CLEAR_KEY)


class PaperAuthorityIssuerError(RuntimeError):
    """Raised when the issuer refuses to sign. Never returns a half-built intent."""


@dataclass(frozen=True)
class PaperGateEvaluators:
    """Callables the issuer invokes itself; never caller-supplied booleans.

    Each callable must accept the complete order request and return a dict with
    an ``approved`` bool and a ``reason`` str, or raise. A callable may also
    return None to signal "cannot evaluate", which the issuer treats as a
    denial (fail closed).
    """

    r7: Callable[[Mapping[str, Any]], Optional[Mapping[str, Any]]]
    antibleed: Callable[[Mapping[str, Any]], Optional[Mapping[str, Any]]]
    risk_governor: Callable[[Mapping[str, Any]], Optional[Mapping[str, Any]]]
    kill_switch: Callable[[Mapping[str, Any]], Optional[Mapping[str, Any]]]


def _require_str(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise PaperAuthorityIssuerError(f"intent identifier required: {name}")
    return value


def _require_positive_decimal_str(value: Any, name: str) -> str:
    from decimal import Decimal, InvalidOperation

    if type(value) is not str:
        raise PaperAuthorityIssuerError(f"canonical decimal must be string: {name}")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise PaperAuthorityIssuerError(f"invalid amount: {name}") from exc
    if not amount.is_finite() or amount <= 0:
        raise PaperAuthorityIssuerError(f"amount must be positive finite: {name}")
    return value


class PaperAuthorityIssuer:
    """Signs paper intents. Never grants execution authority."""

    def __init__(
        self,
        *,
        signing_key: Ed25519PrivateKey,
        issuer_id: str,
        candidate_sha: str,
    ) -> None:
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise PaperAuthorityIssuerError("Ed25519PrivateKey required")
        self.signing_key = signing_key
        self.issuer_id = _require_str(issuer_id, "issuer_id")
        if len(_require_str(candidate_sha, "candidate_sha")) != 40 or any(
            c not in "0123456789abcdef" for c in candidate_sha
        ):
            raise PaperAuthorityIssuerError("candidate_sha must be 40-char lowercase hex")
        self.candidate_sha = candidate_sha

    def issue_paper_intent(
        self,
        *,
        order_request: Mapping[str, Any],
        evaluators: PaperGateEvaluators,
        issued_at: Optional[datetime] = None,
        expires_in_seconds: int = INTENT_EXPIRY_SECONDS,
        now_for_nonce: Optional[datetime] = None,
    ) -> tuple[dict[str, Any], bytes]:
        """Build and sign a paper intent from internal evaluator results only.

        Returns ``(payload, signature)``. Raises ``PaperAuthorityIssuerError``
        on any missing/failed evaluator result — never returns a partially
        populated intent.
        """
        now = issued_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise PaperAuthorityIssuerError("aware issued_at required")
        if expires_in_seconds <= 0 or expires_in_seconds > INTENT_EXPIRY_SECONDS:
            raise PaperAuthorityIssuerError(f"expiry window must be <= {INTENT_EXPIRY_SECONDS}s")
        expires = now + timedelta(seconds=expires_in_seconds)

        # Invoke each evaluator. A None result or ``approved != True`` denies.
        gate_results: dict[str, dict[str, Any]] = {}
        for name, evaluator in (
            (_R7_KEY, evaluators.r7),
            (_ANTIBLEED_KEY, evaluators.antibleed),
            (_RISK_GOVERNOR_KEY, evaluators.risk_governor),
            (_KILL_SWITCH_CLEAR_KEY, evaluators.kill_switch),
        ):
            try:
                result = evaluator(order_request)
            except Exception as exc:
                log.warning("PaperAuthorityIssuer evaluator raised name=%s exc=%r", name, exc)
                raise PaperAuthorityIssuerError(f"evaluator_error:{name}") from exc
            if type(result) is not dict:
                log.warning("PaperAuthorityIssuer evaluator returned non-dict name=%s", name)
                raise PaperAuthorityIssuerError(f"evaluator_unavailable:{name}")
            if result.get("approved") is not True:
                log.warning(
                    "PaperAuthorityIssuer evaluator denied name=%s reason=%r",
                    name,
                    result.get("reason"),
                )
                raise PaperAuthorityIssuerError(
                    f"evaluator_denied:{name}:{result.get('reason', 'unspecified')}"
                )
            gate_results[name] = result

        # Required identifier fields — all must come from the order request.
        parent_id = _require_str(order_request.get("parent_id"), "parent_id")
        child_id = _require_str(order_request.get("child_id"), "child_id")
        broker = _require_str(order_request.get("broker"), "broker")
        account = _require_str(order_request.get("account"), "account")
        instrument = _require_str(order_request.get("instrument"), "instrument")
        side = _require_str(order_request.get("side"), "side")
        if side not in ("BUY", "SELL"):
            raise PaperAuthorityIssuerError("side must be BUY or SELL")
        quote_currency = _require_str(order_request.get("quote_currency"), "quote_currency")
        risk_currency = _require_str(order_request.get("risk_currency"), "risk_currency")
        candidate_sha = _require_str(order_request.get("candidate_sha"), "order candidate_sha")
        if candidate_sha != self.candidate_sha:
            raise PaperAuthorityIssuerError(
                f"candidate_sha_mismatch:order={candidate_sha} issuer={self.candidate_sha}"
            )

        # Numeric fields — canonical decimal strings from the order request.
        quantity = _require_positive_decimal_str(order_request.get("quantity"), "quantity")
        limit_price = _require_positive_decimal_str(order_request.get("limit_price"), "limit_price")
        risk_amount = _require_positive_decimal_str(order_request.get("risk_amount"), "risk_amount")

        # Fresh, non-deterministic nonce. We do not sign reused nonce values.
        nonce_seed = f"{self.issuer_id}:{child_id}:{now_for_nonce or now}"
        nonce = hashlib.sha256(
            (nonce_seed + secrets.token_hex(8)).encode("utf-8")
        ).hexdigest()

        payload = {
            "mode": "PAPER",
            "candidate_sha": self.candidate_sha,
            "broker": broker,
            "account": account,
            "instrument": instrument,
            "parent_id": parent_id,
            "child_id": child_id,
            "side": side,
            "quantity": quantity,
            "limit_price": limit_price,
            "quote_currency": quote_currency,
            "risk_currency": risk_currency,
            "risk_amount": risk_amount,
            "issued_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "nonce": nonce,
            "r7": True,
            "antibleed": True,
            "risk_governor": True,
            "kill_switch_clear": True,
        }

        try:
            digest = canonical_paper_intent_digest(payload)
        except ValueError as exc:
            log.error("PaperAuthorityIssuer digest failed: %s", exc)
            raise PaperAuthorityIssuerError(f"digest_error:{exc}") from exc
        signature = self.signing_key.sign(digest)
        log.info(
            "PaperAuthorityIssuer issued paper intent child_id=%s issuer=%s",
            child_id,
            self.issuer_id,
        )
        return payload, signature


def public_key_bytes_for(signing_key: Ed25519PrivateKey) -> bytes:
    """Helper for fixtures: extract the raw Ed25519 public key bytes."""
    if not isinstance(signing_key, Ed25519PrivateKey):
        raise PaperAuthorityIssuerError("Ed25519PrivateKey required")
    from cryptography.hazmat.primitives import serialization

    return signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
