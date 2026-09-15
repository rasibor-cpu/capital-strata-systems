from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Tuple

from backend.commercialization.independent_trade_economics import (
    IndependentTradeEconomics,
    build_independent_trade_economics,
)
from backend.commercialization.trade_provenance import TradeProvenance


class IndependentPlatformChargeModel(str, Enum):
    DISABLED = "DISABLED"
    POSITIVE_REALIZED_PERCENTAGE = "POSITIVE_REALIZED_PERCENTAGE"


@dataclass(frozen=True, slots=True)
class IndependentPlatformChargePolicy:
    policy_id: str
    model: IndependentPlatformChargeModel
    rate: Decimal
    currency: str
    approved_for_production: bool
    approved_at: str | None
    approval_reference: str | None
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.policy_id or self.policy_id != self.policy_id.strip():
            raise ValueError("policy_id is required and must be canonical")
        if not isinstance(self.model, IndependentPlatformChargeModel):
            raise TypeError("model must be IndependentPlatformChargeModel")
        if not isinstance(self.rate, Decimal) or not self.rate.is_finite():
            raise TypeError("rate must be a finite Decimal")
        if self.rate < Decimal("0") or self.rate > Decimal("1"):
            raise ValueError("rate must be between 0 and 1")
        if not self.currency or self.currency != self.currency.strip() or self.currency != self.currency.upper():
            raise ValueError("currency must be canonical uppercase text")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("evidence_refs must be a non-empty immutable tuple")

        if self.model == IndependentPlatformChargeModel.DISABLED and self.rate != Decimal("0"):
            raise ValueError("DISABLED policy must use zero rate")

        if self.approved_for_production:
            if self.model == IndependentPlatformChargeModel.DISABLED:
                raise ValueError("DISABLED policy cannot be approved for charging")
            if not self.approved_at or not self.approval_reference:
                raise ValueError(
                    "production-approved policy requires approval timestamp and reference"
                )


def build_policy_governed_independent_trade_economics(
    provenance: TradeProvenance,
    *,
    account_reference: str,
    calculation_timestamp: str,
    realized_pnl: Decimal,
    currency: str,
    policy: IndependentPlatformChargePolicy,
    evidence_refs: Tuple[str, ...],
) -> IndependentTradeEconomics:
    if not isinstance(policy, IndependentPlatformChargePolicy):
        raise TypeError("policy must be IndependentPlatformChargePolicy")
    if currency != policy.currency:
        raise ValueError("trade currency must match independent charge policy currency")
    if policy.model == IndependentPlatformChargeModel.DISABLED:
        raise ValueError("independent platform charging policy is disabled")
    if not policy.approved_for_production:
        raise ValueError("independent platform charging policy is not production approved")

    return build_independent_trade_economics(
        provenance,
        account_reference=account_reference,
        calculation_timestamp=calculation_timestamp,
        realized_pnl=realized_pnl,
        currency=currency,
        platform_charge_rate=policy.rate,
        evidence_refs=tuple(dict.fromkeys((*policy.evidence_refs, *evidence_refs))),
    )
