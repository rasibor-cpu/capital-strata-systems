"""Trusted paper authority for governed paper-route simulation (CSS-062).

This module enforces mandatory trusted mode for the governed paper-route
simulation. There is NO caller-selectable untrusted compatibility mode: the
trusted issuer ONLY accepts a ``TrustedRiskEvaluators`` allow-list adapter
bundle, never raw ``PaperGateEvaluators`` callables.

All decisions are fail-closed. Nothing here grants live-execution, broker, or
trading authority.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.runtime.paper_authority_issuer import (
    PaperAuthorityIssuerError,
)
from backend.runtime.trusted_risk_evaluators import (
    TRUSTED_EVALUATOR_IDENTIFIERS,
    TrustedEvaluatorError,
    TrustedRiskEvaluators,
)

__all__ = [
    "TrustedPaperAuthority",
    "TrustedPaperAuthorityError",
    "TRUSTED_AUTHORITY_MAX_TTL_SECONDS",
]

TRUSTED_AUTHORITY_MAX_TTL_SECONDS = 120


class TrustedPaperAuthorityError(RuntimeError):
    """Raised when the trusted authority refuses to sign. Never grants authority."""


class TrustedPaperAuthority:
    """Mandatory trusted-mode issuer. Signs paper intents using allow-list adapters.

    Constructed at trusted-application initialization with:
    - an Ed25519 private key (held only in memory; never persisted);
    - an issuer_id (immutable once bound);
    - a candidate_sha (40-char lowercase hex; immutable once bound).

    The trusted issuer REFUSES to accept raw ``PaperGateEvaluators`` callables.
    """

    def __init__(
        self,
        *,
        signing_key: Ed25519PrivateKey,
        issuer_id: str,
        candidate_sha: str,
        evaluators: TrustedRiskEvaluators,
    ) -> None:
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise TrustedPaperAuthorityError("Ed25519PrivateKey required")
        if not isinstance(evaluators, TrustedRiskEvaluators):
            raise TrustedPaperAuthorityError(
                "TrustedRiskEvaluators required (raw callables are NOT accepted in trusted mode)"
            )
        self.signing_key = signing_key
        self.issuer_id = self._require_identifier(issuer_id, "issuer_id")
        self.candidate_sha = self._require_candidate_sha(candidate_sha)
        self._evaluators = evaluators

    @staticmethod
    def _require_identifier(value: Any, name: str) -> str:
        if type(value) is not str or not value.strip():
            raise TrustedPaperAuthorityError(f"identifier required: {name}")
        return value.strip()

    @staticmethod
    def _require_candidate_sha(value: Any) -> str:
        sha = str(value or "").strip().lower()
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
            raise TrustedPaperAuthorityError("candidate_sha must be 40-char lowercase hex")
        return sha

    @staticmethod
    def _require_positive_decimal(value: Any, name: str) -> float:
        if not isinstance(value, (int, float)) or not float(value) > 0:
            raise TrustedPaperAuthorityError(f"positive finite decimal required: {name}")
        return float(value)

    def _evaluate_all_fail_closed(
        self,
        order_context: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Evaluate all four allow-list gates. Any denial or error fails closed."""
        results = self._evaluators.evaluate_all(order_context)
        for identifier in TRUSTED_EVALUATOR_IDENTIFIERS:
            result = results.get(identifier)
            if not isinstance(result, Mapping):
                raise TrustedPaperAuthorityError(f"missing evaluator result: {identifier}")
            if bool(result.get("approved", False)) is not True:
                raise TrustedPaperAuthorityError(
                    f"gate denied: {identifier} reason={result.get('reason', 'unknown')}"
                )
        return results

    def issue_trusted_paper_intent(
        self,
        *,
        nonce: str,
        expiry_seconds: int = TRUSTED_AUTHORITY_MAX_TTL_SECONDS,
        order_context: Mapping[str, Any],
        paper_route_audience: str,
        actual_candidate_sha: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Issue a signed, trusted paper intent bound to the actual order context.

        The signature binds:
        - issuer identity (self.issuer_id) and key;
        - the paper-only audience;
        - the candidate SHA (bound at construction AND re-verified against
          ``actual_candidate_sha`` to detect a drifted checkout);
        - the nonce (unique per intent);
        - the expiry (capped at TRUSTED_AUTHORITY_MAX_TTL_SECONDS);
        - the complete order+CAD-risk context used to evaluate the gates;
        - the per-gate evaluated decisions (fail-closed summary).
        """
        if expiry_seconds <= 0 or expiry_seconds > TRUSTED_AUTHORITY_MAX_TTL_SECONDS:
            raise TrustedPaperAuthorityError(
                f"expiry_seconds must be in (0, {TRUSTED_AUTHORITY_MAX_TTL_SECONDS}]"
            )
        if str(actual_candidate_sha or "").strip().lower() != self.candidate_sha:
            raise TrustedPaperAuthorityError(
                "CANDIDATE_SHA_MISMATCH: the running checkout does not match the bound trusted SHA"
            )
        if not isinstance(paper_route_audience, str) or not paper_route_audience.strip():
            raise TrustedPaperAuthorityError("paper_route_audience required")

        try:
            gate_results = self._evaluate_all_fail_closed(order_context)
        except TrustedPaperAuthorityError:
            raise
        except Exception as exc:
            raise TrustedPaperAuthorityError(f"trusted evaluation failed closed: {exc}") from exc

        nonce = self._require_identifier(nonce, "nonce")
        now_value = now or datetime.now(timezone.utc)
        expires_at = now_value + timedelta(seconds=expiry_seconds)

        payload = {
            "v": 1,
            "kind": "trusted_paper_intent",
            "issuer_id": self.issuer_id,
            "candidate_sha": self.candidate_sha,
            "paper_route_audience": paper_route_audience.strip(),
            "nonce": nonce,
            "issued_at": now_value.isoformat(),
            "expires_at": expires_at.isoformat(),
            "order_context": self._canonicalize_mapping(order_context),
            "gate_decisions": {
                identifier: {
                    "approved": bool(result.get("approved", False)),
                    "reason": str(result.get("reason", "")),
                }
                for identifier, result in gate_results.items()
            },
        }
        payload_bytes = self._canonical_json(payload).encode("utf-8")
        signature = self.signing_key.sign(payload_bytes)
        return {
            "payload": payload,
            "signature": signature.hex(),
            "algorithm": "Ed25519",
        }

    @staticmethod
    def _canonicalize_mapping(value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise TrustedPaperAuthorityError("canonicalization requires a Mapping")
        return {str(k): TrustedPaperAuthority._canonicalize_value(v) for k, v in sorted(value.items())}

    @staticmethod
    def _canonicalize_value(value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, Mapping):
            return {str(k): TrustedPaperAuthority._canonicalize_value(v) for k, v in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [TrustedPaperAuthority._canonicalize_value(v) for v in value]
        return str(value)

    @staticmethod
    def _canonical_json(payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def verify_trusted_intent(
        intent: Mapping[str, Any],
        *,
        public_key: Ed25519PublicKey,
        expected_issuer_id: str,
        expected_candidate_sha: str,
        expected_paper_route_audience: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Verify a trusted intent. Fail-closed on ANY discrepancy."""
        try:
            payload = intent.get("payload")
            signature_hex = intent.get("signature")
            if not isinstance(payload, Mapping) or not isinstance(signature_hex, str):
                raise TrustedPaperAuthorityError("malformed intent")
            if payload.get("kind") != "trusted_paper_intent":
                raise TrustedPaperAuthorityError("wrong intent kind")
            if payload.get("issuer_id") != expected_issuer_id:
                raise TrustedPaperAuthorityError("issuer_id mismatch")
            if str(payload.get("candidate_sha") or "").lower() != str(expected_candidate_sha).lower():
                raise TrustedPaperAuthorityError("candidate_sha mismatch")
            if payload.get("paper_route_audience") != expected_paper_route_audience:
                raise TrustedPaperAuthorityError("paper_route_audience mismatch")
            now_value = now or datetime.now(timezone.utc)
            expires_at = datetime.fromisoformat(str(payload.get("expires_at")))
            if expires_at <= now_value:
                raise TrustedPaperAuthorityError("intent expired")
            # Verify the gate decisions all approved (fail closed).
            decisions = payload.get("gate_decisions")
            if not isinstance(decisions, Mapping):
                raise TrustedPaperAuthorityError("gate_decisions missing")
            for identifier in TRUSTED_EVALUATOR_IDENTIFIERS:
                decision = decisions.get(identifier)
                if not isinstance(decision, Mapping) or bool(decision.get("approved", False)) is not True:
                    raise TrustedPaperAuthorityError(f"gate not approved: {identifier}")
            # Verify signature.
            signature = bytes.fromhex(signature_hex)
            payload_bytes = TrustedPaperAuthority._canonical_json(dict(payload)).encode("utf-8")
            public_key.verify(signature, payload_bytes)
            return {
                "verified": True,
                "nonce": str(payload.get("nonce")),
                "expires_at": str(payload.get("expires_at")),
            }
        except TrustedPaperAuthorityError:
            raise
        except Exception as exc:
            raise TrustedPaperAuthorityError(f"verification failed: {exc}") from exc
