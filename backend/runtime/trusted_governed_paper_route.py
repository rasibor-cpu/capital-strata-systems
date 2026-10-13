"""Trusted governed paper-route simulation (CSS-062).

This module wires the trusted paper authority (mandatory trusted mode) and
the authoritative coordination ledger into a single simulation entry point.
It is a SIMULATION-ONLY path and does NOT replace the production
``submit_governed_paper_order`` (which remains unconditionally blocked).

CSS-062 Blocker 3 fixes (signed order and risk binding):
- The evaluated and signed ``order_context`` is the SINGLE source of truth
  for parent_id, child_id, proposed CAD exposure, fees, and quantity. The
  route does NOT independently accept these values.
- Capacity limits come from ``CanonicalOrderLimitConfig`` (trusted policy),
  NOT from caller input. No caller can raise the CAD 20/40/2-parent ceilings
  or supply ``None`` to bypass a check.
- The route VERIFIES the signed intent (``verify_trusted_intent``) BEFORE
  reserving capacity (Blocker 2).

CSS-062 Blocker 5 fixes (outcomes and crash consistency):
- ``broker_outcome`` is NOT a caller-supplied string. The route requires a
  ``LocalSimulatorOutcomeEvidence`` record of that exact type, bound to the
  child_id, whose outcome must match the transition (fill -> commit only,
  no-fill -> release only). It is a typed in-process record, NOT a
  cryptographic attestation (see its docstring).
- Unknown outcomes PRESERVE the reservation (no release).
- Confirmed no-fill releases capacity but the nonce stays consumed.
- Confirmed fill commits the reservation.
- A commit-acknowledgment uncertainty is reconciled via the durable
  coordination record — it is NEVER converted into an assumed denial.

Nothing here grants live-execution, broker, or trading authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.config.order_limit_config import CanonicalOrderLimitConfig
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.runtime.pilot_coordination_ledger import (
    AuthoritativePilotCoordinationLedger,
    CoordinationReceipt,
    LocalSimulatorOutcomeEvidence,
)
from backend.runtime.paper_authority_issuer import PaperGateEvaluators
from backend.runtime.trusted_paper_authority import (
    AuthenticatedTrustRegistry,
    TrustedPaperAuthority,
    TrustedPaperAuthorityError,
)
from backend.runtime.trusted_risk_evaluators import TrustedRiskEvaluators

__all__ = [
    "simulate_trusted_governed_paper_order",
    "TrustedSimulationBlocked",
    "LocalSimulatorOutcomeEvidence",
    "TRUSTED_SIMULATION_MAX_TTL_SECONDS",
]


class TrustedSimulationBlocked(RuntimeError):
    """Raised when the trusted simulation rejects an order. Never grants authority."""


TRUSTED_SIMULATION_MAX_TTL_SECONDS = 120


# ``LocalSimulatorOutcomeEvidence`` now lives in pilot_coordination_ledger
# (the ledger enforces its exact type) and is re-exported here unchanged.


def simulate_trusted_governed_paper_order(
    *,
    ledger: AuthoritativePilotCoordinationLedger,
    trusted_authority: TrustedPaperAuthority,
    approval_id: str,
    nonce: str,
    order_context: Mapping[str, Any],
    paper_route_audience: str,
    simulator_evidence: LocalSimulatorOutcomeEvidence | None = None,
) -> dict[str, Any]:
    """Trusted simulation entry point. Mandatory trusted mode; fail closed.

    The ``order_context`` is the SINGLE source of truth for the order and
    risk envelope. The route extracts parent_id, child_id, proposed CAD,
    and fees FROM the order_context — it does NOT accept them separately.

    Steps:
    1. Issue a trusted paper intent (verifies the ACTUAL checkout SHA and
       evaluates all four gates, fail-closed).
    2. VERIFY the signed intent (fail-closed) BEFORE reserving capacity.
    3. Atomically consume the nonce AND reserve exposure in ONE transaction
       (capacity limits from trusted policy, not caller input).
    4. If the simulator outcome is UNKNOWN (no evidence), PRESERVE the
       reservation (no release).
    5. If the simulator outcome is confirmed no-fill, release capacity (the
       nonce stays consumed).
    6. If the simulator outcome is confirmed fill, commit the reservation.
    """
    # --- 0) Reject raw callables and non-trusted authority (Blocker 2) ----
    if isinstance(trusted_authority, PaperGateEvaluators):
        raise TrustedSimulationBlocked("PAPER_SIMULATION_TRUSTED_MODE_REQUIRED")
    if not isinstance(trusted_authority, TrustedPaperAuthority):
        raise TrustedSimulationBlocked("PAPER_SIMULATION_TRUSTED_MODE_REQUIRED")

    # --- 1) Issue the trusted paper intent (fail-closed; verifies checkout) ---
    try:
        intent = trusted_authority.issue_trusted_paper_intent(
            nonce=str(nonce),
            order_context=order_context,
            paper_route_audience=str(paper_route_audience),
        )
    except TrustedPaperAuthorityError as exc:
        raise TrustedSimulationBlocked(f"PAPER_SIMULATION_TRUSTED_INTENT_REJECTED:{exc}") from exc

    # --- 2) VERIFY the signed intent BEFORE reserving capacity (Blocker 2) ---
    try:
        # Verify against the PINNED public key recorded in the registry, not a
        # key derived from the signer's own private key object.
        pinned_public_key = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(trusted_authority.registry.public_key_hex)
        )
        verification = TrustedPaperAuthority.verify_trusted_intent(
            intent,
            public_key=pinned_public_key,
            expected_issuer_id=trusted_authority.issuer_id,
            expected_candidate_sha=trusted_authority.candidate_sha,
            expected_paper_route_audience=str(paper_route_audience),
        )
    except (TrustedPaperAuthorityError, ValueError) as exc:
        raise TrustedSimulationBlocked(f"PAPER_SIMULATION_INTENT_VERIFICATION_FAILED:{exc}") from exc

    # --- 3) Extract the binding values FROM the signed order_context (Blocker 3) ---
    # Independent review fix: read the binding from the VERIFIED, SIGNED
    # payload copy — never re-read the caller's (possibly mutable) Mapping
    # after signing.
    signed_payload = intent.get("payload") if isinstance(intent, Mapping) else None
    signed_context = signed_payload.get("order_context") if isinstance(signed_payload, Mapping) else None
    binding = _extract_binding(signed_context)
    if binding is None:
        raise TrustedSimulationBlocked("PAPER_SIMULATION_ORDER_BINDING_INCOMPLETE")

    # --- 4) Atomic nonce + reservation (ONE transaction; trusted policy ceilings) ---
    receipt: CoordinationReceipt = ledger.atomic_consume_and_reserve(
        approval_id=str(approval_id),
        nonce=str(nonce),
        issuer_id=trusted_authority.issuer_id,
        candidate_sha=trusted_authority.candidate_sha,
        parent_id=binding.parent_id,
        child_id=binding.child_id,
        proposed_child_cad=binding.proposed_child_cad,
        estimated_fees_cad=binding.estimated_fees_cad,
    )
    # Do NOT treat a commit-acknowledgment uncertainty as a plain denial, and
    # do NOT act on a simulator outcome in that state: the ledger proved THIS
    # transaction durable, so the reservation is preserved for reconciliation.
    # (Independent review fix: the ledger reports this with success=True, so
    # the check must not be nested under ``not receipt.success``.)
    if receipt.reason == "COORDINATION_COMMIT_ACK_UNCERTAIN":
        return {
            "status": "COMMIT_ACK_UNCERTAIN_RECONCILED",
            "reservation_state": ledger.reservation_state(child_id=binding.child_id),
            "intent_nonce": verification["nonce"],
            "transaction_id": receipt.transaction_id,
        }
    if not receipt.success:
        raise TrustedSimulationBlocked(f"PAPER_SIMULATION_COORDINATION_REJECTED:{receipt.reason}")

    # --- 5) Simulator outcome handling (Blocker 5: verifiable evidence required) ---
    if simulator_evidence is None:
        # UNKNOWN outcome: PRESERVE the reservation; do NOT release.
        return {
            "status": "UNKNOWN_OUTCOME_PRESERVED",
            "reservation_state": ledger.reservation_state(child_id=binding.child_id),
            "intent_nonce": verification["nonce"],
            "transaction_id": receipt.transaction_id,
        }
    # Verifiable simulator evidence is present. The ledger's
    # release_reservation / commit_reservation verify it independently.
    outcome = simulator_evidence.verified_outcome()
    if outcome == "confirmed_no_fill":
        released = ledger.release_reservation(
            child_id=binding.child_id,
            reason="confirmed_no_fill",
            confirmed_by_simulator=simulator_evidence,
        )
        return {
            "status": "NO_FILL_RELEASED" if released else "NO_FILL_RELEASE_FAILED",
            "reservation_state": ledger.reservation_state(child_id=binding.child_id),
            "intent_nonce": verification["nonce"],
            "transaction_id": receipt.transaction_id,
        }
    if outcome == "confirmed_fill":
        committed = ledger.commit_reservation(
            child_id=binding.child_id,
            confirmed_by_simulator=simulator_evidence,
        )
        return {
            "status": "FILLED_COMMITTED" if committed else "COMMIT_FAILED",
            "reservation_state": ledger.reservation_state(child_id=binding.child_id),
            "intent_nonce": verification["nonce"],
            "transaction_id": receipt.transaction_id,
        }
    # Unrecognized outcome → treat as UNKNOWN (fail closed).
    return {
        "status": "UNKNOWN_OUTCOME_PRESERVED",
        "reservation_state": ledger.reservation_state(child_id=binding.child_id),
        "intent_nonce": verification["nonce"],
        "transaction_id": receipt.transaction_id,
    }


@dataclass(frozen=True)
class _OrderBinding:
    parent_id: str
    child_id: str
    proposed_child_cad: str
    estimated_fees_cad: str


def _extract_binding(order_context: Mapping[str, Any]) -> _OrderBinding | None:
    """Extract the parent/child/CAD/fees binding FROM the signed order_context.

    The order_context is the SINGLE source of truth (Blocker 3). We do NOT
    accept these values as separate function arguments.
    """
    if not isinstance(order_context, Mapping):
        return None
    parent_id = order_context.get("parent_id")
    child_id = order_context.get("child_id")
    proposed_cad = order_context.get("proposed_child_cad")
    fees = order_context.get("estimated_fees_cad")
    if not isinstance(parent_id, str) or not parent_id.strip():
        return None
    if not isinstance(child_id, str) or not child_id.strip():
        return None
    for v in (proposed_cad, fees):
        if isinstance(v, bool) or not isinstance(v, (int, float, str, Decimal)):
            return None
    return _OrderBinding(
        parent_id=parent_id.strip(),
        child_id=child_id.strip(),
        proposed_child_cad=str(proposed_cad),
        estimated_fees_cad=str(fees),
    )
