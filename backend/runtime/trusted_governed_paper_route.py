"""Trusted governed paper-route simulation (CSS-062).

This module wires the trusted paper authority (mandatory trusted mode) and the
atomic coordination ledger into a single simulation entry point. It is a
SIMULATION-ONLY path and does NOT replace the production
``submit_governed_paper_order`` (which remains unconditionally blocked).

The trusted simulation:
1. Rejects raw ``PaperGateEvaluators`` callables (mandatory trusted mode).
2. Uses the closed allow-list ``TrustedRiskEvaluators`` for all four gates.
3. Uses the atomic ``PilotCoordinationLedger`` for nonce + reservation in ONE
   SQLite transaction (no claim-file replay authority).
4. Does NOT release the reservation when the broker outcome is unknown.

Nothing here grants live-execution, broker, or trading authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.runtime.pilot_coordination_ledger import (
    CoordinationReceipt,
    PilotCoordinationLedger,
)
from backend.runtime.paper_authority_issuer import PaperGateEvaluators
from backend.runtime.paper_authority_registry import PaperIssuerRegistry
from backend.runtime.trusted_paper_authority import (
    TrustedPaperAuthority,
    TrustedPaperAuthorityError,
)
from backend.runtime.trusted_risk_evaluators import TrustedRiskEvaluators

__all__ = [
    "simulate_trusted_governed_paper_order",
    "TrustedSimulationBlocked",
    "TRUSTED_SIMULATION_MAX_TTL_SECONDS",
]


class TrustedSimulationBlocked(RuntimeError):
    """Raised when the trusted simulation rejects an order. Never grants authority."""


TRUSTED_SIMULATION_MAX_TTL_SECONDS = 120


def simulate_trusted_governed_paper_order(
    *,
    ledger: PilotCoordinationLedger,
    trusted_authority: TrustedPaperAuthority,
    approval_id: str,
    nonce: str,
    order_context: Mapping[str, Any],
    paper_route_audience: str,
    actual_candidate_sha: str,
    child_id: str,
    parent_id: str,
    proposed_child_cad: Any,
    estimated_fees_cad: Any,
    max_parent_cad: Decimal = Decimal("20.00"),
    max_total_cad: Decimal("40.00"),
    max_concurrent_parents: int = 2,
    broker_outcome: str = "unknown",
    fake_broker: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Trusted simulation entry point. Mandatory trusted mode; fail closed.

    Steps:
    1. Issue a trusted paper intent using the allow-list evaluators (fail-closed).
    2. Atomically consume the nonce AND reserve exposure in ONE transaction.
    3. If the broker outcome is UNKNOWN, the reservation is PRESERVED (no release).
    4. If the broker outcome is confirmed no-fill, capacity may be released.
    5. If the broker outcome is confirmed fill, the reservation is COMMITTED.

    The production route is NOT modified; it stays unconditionally blocked.
    """
    # --- 0) Reject raw callables (mandatory trusted mode) -------------------
    if isinstance(trusted_authority, PaperGateEvaluators):
        raise TrustedSimulationBlocked("PAPER_SIMULATION_TRUSTED_MODE_REQUIRED")

    # --- 1) Issue the trusted paper intent (fail-closed) -------------------
    try:
        intent = trusted_authority.issue_trusted_paper_intent(
            nonce=str(nonce),
            order_context=order_context,
            paper_route_audience=str(paper_route_audience),
            actual_candidate_sha=str(actual_candidate_sha),
            now=now,
        )
    except TrustedPaperAuthorityError as exc:
        raise TrustedSimulationBlocked(f"PAPER_SIMULATION_TRUSTED_INTENT_REJECTED:{exc}") from exc

    # --- 2) Atomic nonce + reservation (ONE SQLite transaction) -------------
    receipt: CoordinationReceipt = ledger.atomic_consume_and_reserve(
        approval_id=str(approval_id),
        nonce=str(nonce),
        issuer_id=trusted_authority.issuer_id,
        candidate_sha=trusted_authority.candidate_sha,
        parent_id=str(parent_id),
        child_id=str(child_id),
        proposed_child_cad=proposed_child_cad,
        estimated_fees_cad=estimated_fees_cad,
        max_parent_cad=max_parent_cad,
        max_total_cad=max_total_cad,
        max_concurrent_parents=max_concurrent_parents,
    )
    if not receipt.success:
        raise TrustedSimulationBlocked(f"PAPER_SIMULATION_COORDINATION_REJECTED:{receipt.reason}")

    # --- 3) Broker outcome handling ----------------------------------------
    outcome = str(broker_outcome).strip().lower()
    if outcome == "unknown":
        # PRESERVE the reservation; do NOT release. A retry with the same
        # nonce is rejected (replay).
        return {
            "status": "UNKNOWN_OUTCOME_PRESERVED",
            "reservation_state": ledger.reservation_state(child_id=str(child_id)),
            "intent_nonce": str(intent["payload"]["nonce"]),
            "transaction_id": receipt.transaction_id,
        }
    if outcome in {"no_fill", "no-fill", "rejected", "not_filled"}:
        released = ledger.release_reservation(
            child_id=str(child_id),
            reason=f"confirmed_no_fill:{outcome}",
        )
        return {
            "status": "NO_FILL_RELEASED" if released else "NO_FILL_RELEASE_FAILED",
            "reservation_state": ledger.reservation_state(child_id=str(child_id)),
            "intent_nonce": str(intent["payload"]["nonce"]),
            "transaction_id": receipt.transaction_id,
        }
    if outcome in {"fill", "filled", "confirmed_fill"}:
        committed = ledger.commit_reservation(child_id=str(child_id))
        return {
            "status": "FILLED_COMMITTED" if committed else "COMMIT_FAILED",
            "reservation_state": ledger.reservation_state(child_id=str(child_id)),
            "intent_nonce": str(intent["payload"]["nonce"]),
            "transaction_id": receipt.transaction_id,
        }
    # Any unrecognized outcome is treated as UNKNOWN (fail closed).
    return {
        "status": "UNKNOWN_OUTCOME_PRESERVED",
        "reservation_state": ledger.reservation_state(child_id=str(child_id)),
        "intent_nonce": str(intent["payload"]["nonce"]),
        "transaction_id": receipt.transaction_id,
    }
