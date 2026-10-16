"""Governed CAD pilot envelope: CAD 20 per parent, CAD 40 aggregate, two concurrent parents.

Ported from the draft pilot work (PR #105 / #106, `backend/runtime/pilot_portfolio_limit.py`)
with one deliberate difference: it does NOT raise the canonical live caps in
`backend/config/order_limit_config.py` (CAD 20 total, 1 position), which keep governing
the live micro-pilot unchanged. This envelope is an additional, independent ceiling for
pilot-scope paper accounts; most restrictive wins.

Per parent: committed + pending + estimated fees <= CAD 20.00 (the existing per-parent
ceiling). Aggregate across open parents <= CAD 40.00. At most 2 concurrent parents.
Values are fixed ceilings: configuration may tighten them but never raise them.
Fails closed on malformed state, duplicate parents, non-CAD currency or bad amounts.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

_CENT = Decimal("0.01")
APPROVED_MAX_PARENT_CAD = Decimal("20.00")
APPROVED_MAX_TOTAL_CAD = Decimal("40.00")
APPROVED_MAX_CONCURRENT_PARENTS = 2


def money(raw: Any) -> Decimal:
    if isinstance(raw, bool):
        raise ValueError("boolean amount not permitted")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid money amount") from exc
    if not value.is_finite() or value < 0:
        raise ValueError("amount must be finite and non-negative")
    if value != value.quantize(_CENT):
        raise ValueError("amount must be whole cents")
    return value


@dataclass(frozen=True)
class PilotEnvelopeConfig:
    max_parent_cad: Decimal = APPROVED_MAX_PARENT_CAD
    max_total_cad: Decimal = APPROVED_MAX_TOTAL_CAD
    max_concurrent_parents: int = APPROVED_MAX_CONCURRENT_PARENTS

    def validate(self) -> None:
        for value, ceiling, name in ((self.max_parent_cad, APPROVED_MAX_PARENT_CAD, "max_parent_cad"),
                                     (self.max_total_cad, APPROVED_MAX_TOTAL_CAD, "max_total_cad")):
            if type(value) is not Decimal or money(value) <= 0 or value > ceiling:
                raise ValueError(f"{name} must be positive and <= {ceiling}")
        if (isinstance(self.max_concurrent_parents, bool) or not isinstance(self.max_concurrent_parents, int)
                or not 1 <= self.max_concurrent_parents <= APPROVED_MAX_CONCURRENT_PARENTS):
            raise ValueError("max_concurrent_parents must be 1..2")
        if self.max_parent_cad > self.max_total_cad:
            raise ValueError("parent ceiling cannot exceed aggregate ceiling")


DEFAULT_PILOT_ENVELOPE = PilotEnvelopeConfig()


@dataclass(frozen=True)
class PilotParentExposure:
    parent_id: str
    committed_cad: Decimal
    pending_cad: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        if not isinstance(self.parent_id, str) or not self.parent_id.strip() or self.parent_id != self.parent_id.strip():
            raise ValueError("parent_id required and normalized")
        if type(self.committed_cad) is not Decimal or type(self.pending_cad) is not Decimal:
            raise ValueError("exposure amounts must be Decimal")
        money(self.committed_cad)
        money(self.pending_cad)

    @property
    def open_cad(self) -> Decimal:
        return self.committed_cad + self.pending_cad


@dataclass(frozen=True)
class PilotEnvelopeDecision:
    approved: bool
    reason: str
    parent_id: str
    projected_parent_cad: Decimal
    projected_total_cad: Decimal
    projected_parent_count: int


def evaluate_pilot_envelope(
    existing_parents: Iterable[PilotParentExposure],
    *,
    parent_id: str,
    proposed_child_cad: Any,
    estimated_fees_cad: Any = Decimal("0.00"),
    currency: str = "CAD",
    config: PilotEnvelopeConfig = DEFAULT_PILOT_ENVELOPE,
) -> PilotEnvelopeDecision:
    zero = Decimal("0.00")
    try:
        if str(currency).upper() != "CAD":
            return PilotEnvelopeDecision(False, "PILOT_CURRENCY_NOT_CAD", str(parent_id), zero, zero, 0)
        pid = str(parent_id).strip()
        if not pid:
            raise ValueError("parent_id required")
        proposed = money(proposed_child_cad)
        fees = money(estimated_fees_cad)
        if proposed <= 0:
            raise ValueError("proposed child must be positive")
        if not isinstance(config, PilotEnvelopeConfig):
            raise ValueError("envelope config required")
        config.validate()
        parents = list(existing_parents)
        by_id: dict[str, PilotParentExposure] = {}
        for parent in parents:
            if type(parent) is not PilotParentExposure:
                raise ValueError("invalid parent exposure")
            if parent.parent_id in by_id:
                raise ValueError("duplicate parent exposure")
            if parent.open_cad > config.max_parent_cad:
                raise ValueError("existing parent already exceeds ceiling")
            by_id[parent.parent_id] = parent
        current_total = sum((p.open_cad for p in parents), zero)
        if current_total > config.max_total_cad or len(parents) > config.max_concurrent_parents:
            raise ValueError("existing portfolio already exceeds ceiling")
        current = by_id.get(pid)
        projected_parent = (current.open_cad if current else zero) + proposed + fees
        projected_total = current_total + proposed + fees
        projected_count = len(parents) + (0 if current else 1)
        if projected_parent > config.max_parent_cad:
            return PilotEnvelopeDecision(False, "PILOT_PARENT_EXPOSURE_CEILING", pid, projected_parent, projected_total, projected_count)
        if projected_count > config.max_concurrent_parents:
            return PilotEnvelopeDecision(False, "PILOT_CONCURRENT_PARENT_CEILING", pid, projected_parent, projected_total, projected_count)
        if projected_total > config.max_total_cad:
            return PilotEnvelopeDecision(False, "PILOT_AGGREGATE_EXPOSURE_CEILING", pid, projected_parent, projected_total, projected_count)
        return PilotEnvelopeDecision(True, "PILOT_ENVELOPE_OK", pid, projected_parent, projected_total, projected_count)
    except Exception:
        return PilotEnvelopeDecision(False, "PILOT_ENVELOPE_EVALUATION_ERROR",
                                     str(parent_id).strip() if parent_id is not None else "", zero, zero, 0)


def remaining_parent_budget(existing_parents: Iterable[PilotParentExposure], *,
                            config: PilotEnvelopeConfig = DEFAULT_PILOT_ENVELOPE) -> Decimal:
    """Largest new-parent amount (incl. fees) the envelope can still take; 0 if none."""
    parents = list(existing_parents)
    if len(parents) >= config.max_concurrent_parents:
        return Decimal("0.00")
    total = sum((p.open_cad for p in parents), Decimal("0.00"))
    return max(Decimal("0.00"), min(config.max_parent_cad, config.max_total_cad - total))
