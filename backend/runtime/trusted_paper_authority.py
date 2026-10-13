"""Trusted paper authority for governed paper-route simulation (CSS-062).

This module enforces mandatory trusted mode for the governed paper-route
simulation. There is NO caller-selectable untrusted compatibility mode.

CSS-062 Blocker 2 fixes (remove caller-controlled trust establishment):
- The signing key, issuer_id, candidate_sha and evaluator instance are NOT
  accepted from the per-order caller. They are pinned at trusted-application
  initialization via an ``AuthenticatedTrustRegistry``.
- ``actual_candidate_sha`` is verified against the CURRENT checkout's git
  HEAD SHA (computed from ``.git/HEAD``), NOT against another
  caller-supplied string.
- ``TrustedRiskEvaluators`` is FINAL — subclass substitution is rejected.
- ``verify_trusted_intent()`` is called by the trusted route BEFORE any
  capacity is reserved.

HUMAN ACTION REQUIRED (documented, not invented):
- The ``AuthenticatedTrustRegistry`` must be produced by a HUMAN owner
  reviewing the implementation SHA and issuing a signed manifest. This
  environment cannot invent trusted credentials. When the registry is
  absent, the trusted path stays BLOCKED (fail closed).
- The Ed25519 private key must be generated and held by the owner, never
  persisted in this repository.

Nothing here grants live-execution, broker, or trading authority.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.runtime.trusted_risk_evaluators import (
    TRUSTED_EVALUATOR_IDENTIFIERS,
    TrustedEvaluatorError,
    TrustedRiskEvaluators,
)

__all__ = [
    "TrustedPaperAuthority",
    "TrustedPaperAuthorityError",
    "AuthenticatedTrustRegistry",
    "TRUSTED_AUTHORITY_MAX_TTL_SECONDS",
]

TRUSTED_AUTHORITY_MAX_TTL_SECONDS = 120


class TrustedPaperAuthorityError(RuntimeError):
    """Raised when the trusted authority refuses to sign. Never grants authority."""


def compute_current_checkout_sha(repo_root: Path | str | None = None) -> str | None:
    """Compute the current checkout's git HEAD SHA (40-char lowercase hex).

    Returns ``None`` if the repository root or HEAD cannot be determined.
    This is the ACTUAL checkout SHA, not a caller-supplied string.
    """
    if repo_root is None:
        # Walk up from this file to find the repo root.
        current = Path(__file__).resolve()
        for candidate in current.parents:
            if (candidate / ".git").exists():
                repo_root = candidate
                break
        else:
            return None
    git_dir = Path(repo_root) / ".git"
    if not git_dir.exists():
        return None
    if git_dir.is_file():
        # Worktree: .git is a file pointing to the real git dir.
        content = git_dir.read_text(encoding="utf-8").strip()
        if content.startswith("gitdir:"):
            git_dir = Path(content.split(":", 1)[1].strip())
    head_file = git_dir / "HEAD"
    if not head_file.exists():
        return None
    head = head_file.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref_path = git_dir / head[4:].strip()
        if not ref_path.exists():
            return None
        sha = ref_path.read_text(encoding="utf-8").strip()
    else:
        sha = head
    sha = sha.strip().lower()
    if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
        return sha
    return None


@dataclass(frozen=True)
class AuthenticatedTrustRegistry:
    """Pinned trust state produced by a HUMAN owner at trusted initialization.

    This dataclass is IMMUTABLE and is the ONLY source of issuer identity,
    candidate SHA, and evaluator ownership. It is NOT constructed from
    per-order caller input.

    HUMAN ACTION REQUIRED to produce this:
    1. The owner reviews the implementation at a specific commit SHA.
    2. The owner generates an Ed25519 keypair OUTSIDE the repository.
    3. The owner records the public key, issuer_id, and the reviewed SHA in
       a signed manifest (e.g. GPG-signed or hardware-signed).
    4. The manifest is loaded at trusted-application initialization.

    This environment does NOT invent these credentials.
    """

    issuer_id: str
    candidate_sha: str
    public_key_hex: str
    private_key: Ed25519PrivateKey = field(repr=False, compare=False)
    created_at: str = ""

    def __post_init__(self) -> None:
        if type(self.issuer_id) is not str or not self.issuer_id.strip():
            raise TrustedPaperAuthorityError("issuer_id required")
        sha = str(self.candidate_sha or "").strip().lower()
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
            raise TrustedPaperAuthorityError("candidate_sha must be 40-char lowercase hex")
        if type(self.public_key_hex) is not str or len(self.public_key_hex) != 64:
            raise TrustedPaperAuthorityError("public_key_hex must be 64-char hex (32-byte Ed25519)")
        if not isinstance(self.private_key, Ed25519PrivateKey):
            raise TrustedPaperAuthorityError("Ed25519PrivateKey required")
        # Verify the private key matches the pinned public key.
        if self.private_key.public_key().public_bytes_raw().hex() != self.public_key_hex:
            raise TrustedPaperAuthorityError("private key does not match pinned public key")


class TrustedPaperAuthority:
    """Mandatory trusted-mode issuer. Signs paper intents using allow-list adapters.

    Constructed at trusted-application initialization with an
    ``AuthenticatedTrustRegistry`` (produced by a HUMAN owner) and a FINAL
    ``TrustedRiskEvaluators`` instance. The per-order caller supplies NONE
    of the trust state.
    """

    def __init__(
        self,
        *,
        registry: AuthenticatedTrustRegistry,
        evaluators: TrustedRiskEvaluators,
        repo_root: Path | str | None = None,
    ) -> None:
        if not isinstance(registry, AuthenticatedTrustRegistry):
            raise TrustedPaperAuthorityError("AuthenticatedTrustRegistry required")
        if type(evaluators) is not TrustedRiskEvaluators:
            # Reject subclasses (CSS-062 Blocker 2: subclass substitution).
            raise TrustedPaperAuthorityError(
                "TrustedRiskEvaluators (final) required — subclass substitution rejected"
            )
        self.registry = registry
        self.issuer_id = registry.issuer_id
        self.candidate_sha = registry.candidate_sha
        self._evaluators = evaluators
        self._repo_root = Path(repo_root) if repo_root is not None else None

    # ------------------------------------------------------- checkout verification
    def _verify_current_checkout(self) -> None:
        """Verify the CURRENT checkout matches the pinned candidate SHA.

        Computes the actual git HEAD SHA (NOT a caller-supplied string) and
        compares it against the registry's pinned ``candidate_sha``. A
        mismatch means the running code is NOT the reviewed implementation.
        """
        actual = compute_current_checkout_sha(self._repo_root)
        if actual is None:
            raise TrustedPaperAuthorityError(
                "CHECKOUT_SHA_UNVERIFIABLE: cannot determine the current git HEAD — trusted path blocked"
            )
        if actual != self.candidate_sha:
            raise TrustedPaperAuthorityError(
                f"CANDIDATE_SHA_MISMATCH: running checkout {actual} != pinned {self.candidate_sha}"
            )

    # ------------------------------------------------------------- issuance
    def issue_trusted_paper_intent(
        self,
        *,
        nonce: str,
        expiry_seconds: int = TRUSTED_AUTHORITY_MAX_TTL_SECONDS,
        order_context: Mapping[str, Any],
        paper_route_audience: str,
    ) -> dict[str, Any]:
        """Issue a signed, trusted paper intent bound to the actual order context.

        The signature binds:
        - issuer identity (from the registry, NOT the caller);
        - the candidate SHA (pinned in the registry AND verified against the
          ACTUAL current checkout);
        - the paper-only audience;
        - the nonce;
        - the expiry (capped at TRUSTED_AUTHORITY_MAX_TTL_SECONDS);
        - the complete order+CAD-risk context;
        - the per-gate evaluated decisions (fail-closed summary).
        """
        if expiry_seconds <= 0 or expiry_seconds > TRUSTED_AUTHORITY_MAX_TTL_SECONDS:
            raise TrustedPaperAuthorityError(
                f"expiry_seconds must be in (0, {TRUSTED_AUTHORITY_MAX_TTL_SECONDS}]"
            )
        if not isinstance(paper_route_audience, str) or not paper_route_audience.strip():
            raise TrustedPaperAuthorityError("paper_route_audience required")

        # Verify the ACTUAL checkout before signing (Blocker 2).
        self._verify_current_checkout()

        # Evaluate all four allow-list gates. Any denial or error fails closed.
        results = self._evaluators.evaluate_all(order_context)
        for identifier in TRUSTED_EVALUATOR_IDENTIFIERS:
            result = results.get(identifier)
            if not isinstance(result, Mapping):
                raise TrustedPaperAuthorityError(f"missing evaluator result: {identifier}")
            approved = result.get("approved", None)
            if approved is not True:  # EXPLICIT boolean (Blocker 4)
                raise TrustedPaperAuthorityError(
                    f"gate denied: {identifier} reason={result.get('reason', 'unknown')}"
                )

        nonce = str(nonce or "").strip()
        if not nonce:
            raise TrustedPaperAuthorityError("nonce required")
        now_value = datetime.now(timezone.utc)
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
                    "approved": True,
                    "reason": str(result.get("reason", "")),
                }
                for identifier, result in results.items()
            },
        }
        payload_bytes = self._canonical_json(payload).encode("utf-8")
        signature = self.registry.private_key.sign(payload_bytes)
        return {
            "payload": payload,
            "signature": signature.hex(),
            "algorithm": "Ed25519",
        }

    # ----------------------------------------------------------- verification
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
        """Verify a trusted intent. Fail-closed on ANY discrepancy.

        Called by the trusted route BEFORE any capacity is reserved
        (CSS-062 Blocker 2).
        """
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
            # Verify the gate decisions all approved with EXPLICIT booleans.
            decisions = payload.get("gate_decisions")
            if not isinstance(decisions, Mapping):
                raise TrustedPaperAuthorityError("gate_decisions missing")
            for identifier in TRUSTED_EVALUATOR_IDENTIFIERS:
                decision = decisions.get(identifier)
                if not isinstance(decision, Mapping):
                    raise TrustedPaperAuthorityError(f"gate decision missing: {identifier}")
                approved = decision.get("approved", None)
                if approved is not True:  # EXPLICIT boolean (Blocker 4)
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

    # ------------------------------------------------------------- canonical
    @staticmethod
    def _canonicalize_mapping(value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise TrustedPaperAuthorityError("canonicalization requires a Mapping")
        return {
            str(k): TrustedPaperAuthority._canonicalize_value(v)
            for k, v in sorted(value.items())
        }

    @staticmethod
    def _canonicalize_value(value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, Mapping):
            return {
                str(k): TrustedPaperAuthority._canonicalize_value(v)
                for k, v in sorted(value.items())
            }
        if isinstance(value, (list, tuple)):
            return [TrustedPaperAuthority._canonicalize_value(v) for v in value]
        return str(value)

    @staticmethod
    def _canonical_json(payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
