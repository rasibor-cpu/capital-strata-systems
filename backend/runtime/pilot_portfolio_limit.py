"""Fail-closed portfolio gate for the governed CAD pilot micro-trading envelope.

This module does not place orders, arm brokers, or grant live-trading authority.
It only evaluates whether a proposed child order remains inside the approved
pilot exposure budget.

Pilot policy encoded here:
- maximum CAD 20 committed+pending+fees per parent exposure;
- maximum 2 concurrent parent exposures;
- maximum CAD 40 total concurrent exposure;
- multiple child orders may contribute to the same parent envelope;
- all limits are ceilings and never override AntiBleedGuard, R7, broker,
  reconciliation, RBAC, kill-switch, or execution-authority controls.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from backend.config.order_limit_config import (
    CanonicalOrderLimitConfig,
    DEFAULT_ORDER_LIMIT_CONFIG,
)


_CENT = Decimal("0.01")


def _money(raw: Any) -> Decimal:
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
class PilotParentExposure:
    parent_id: str
    committed_cad: Decimal
    pending_cad: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        if not isinstance(self.parent_id, str) or not self.parent_id.strip():
            raise ValueError("parent_id required")
        if self.parent_id != self.parent_id.strip():
            raise ValueError("parent_id must be normalized")
        if type(self.committed_cad) is not Decimal or type(self.pending_cad) is not Decimal:
            raise ValueError("exposure amounts must be Decimal")
        _money(self.committed_cad)
        _money(self.pending_cad)

    @property
    def open_cad(self) -> Decimal:
        return self.committed_cad + self.pending_cad


@dataclass(frozen=True)
class PilotPortfolioDecision:
    approved: bool
    reason: str
    parent_id: str
    projected_parent_cad: Decimal
    projected_total_cad: Decimal
    projected_parent_count: int


def evaluate_pilot_portfolio(
    existing_parents: Iterable[PilotParentExposure],
    *,
    parent_id: str,
    proposed_child_cad: Any,
    estimated_fees_cad: Any = Decimal("0.00"),
    config: CanonicalOrderLimitConfig = DEFAULT_ORDER_LIMIT_CONFIG,
) -> PilotPortfolioDecision:
    """Evaluate a child order against parent, concurrency and aggregate ceilings.

    Fail closed on malformed state, duplicate parents, or unsafe configuration.
    The caller remains responsible for all existing execution/risk gates.
    """
    zero = Decimal("0.00")
    try:
        normalized_parent = str(parent_id).strip()
        if not normalized_parent:
            raise ValueError("parent_id required")
        proposed = _money(proposed_child_cad)
        fees = _money(estimated_fees_cad)
        if proposed <= 0:
            raise ValueError("proposed child must be positive")

        if not isinstance(config, CanonicalOrderLimitConfig):
            raise ValueError("canonical config required")
        config.validate()

        parents = list(existing_parents)
        if any(type(p) is not PilotParentExposure for p in parents):
            raise ValueError("invalid parent exposure")
        by_id: dict[str, PilotParentExposure] = {}
        for parent in parents:
            if parent.parent_id in by_id:
                raise ValueError("duplicate parent exposure")
            if parent.open_cad > config.live_pilot_max_position_cad:
                raise ValueError("existing parent already exceeds canonical ceiling")
            by_id[parent.parent_id] = parent

        current_total = sum((p.open_cad for p in parents), zero)
        if current_total > config.live_pilot_max_total_cad:
            raise ValueError("existing portfolio already exceeds canonical ceiling")

        current_parent = by_id.get(normalized_parent)
        existing_parent_cad = current_parent.open_cad if current_parent else zero
        projected_parent = existing_parent_cad + proposed + fees
        projected_total = current_total + proposed + fees
        projected_count = len(parents) + (0 if current_parent else 1)

        if projected_parent > config.live_pilot_max_position_cad:
            return PilotPortfolioDecision(
                False, "PILOT_PARENT_EXPOSURE_CEILING", normalized_parent,
                projected_parent, projected_total, projected_count,
            )
        if projected_count > config.live_pilot_max_concurrent_positions:
            return PilotPortfolioDecision(
                False, "PILOT_CONCURRENT_EXPOSURE_CEILING", normalized_parent,
                projected_parent, projected_total, projected_count,
            )
        if projected_total > config.live_pilot_max_total_cad:
            return PilotPortfolioDecision(
                False, "PILOT_TOTAL_EXPOSURE_CEILING", normalized_parent,
                projected_parent, projected_total, projected_count,
            )

        return PilotPortfolioDecision(
            True, "PILOT_PORTFOLIO_PREFLIGHT_ONLY", normalized_parent,
            projected_parent, projected_total, projected_count,
        )
    except Exception:
        return PilotPortfolioDecision(
            False, "PILOT_PORTFOLIO_EVALUATION_ERROR",
            str(parent_id).strip() if parent_id is not None else "",
            zero, zero, 0,
        )


__all__ = [
    "PilotParentExposure",
    "PilotPortfolioDecision",
    "evaluate_pilot_portfolio",
]
