from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from backend.commercialization.performance_accounting import (
    PerformanceAccountingTransition,
)


class PerformanceCompensationError(ValueError):
    """Base COM-002D compensation-contract error."""


class PerformanceCompensationIneligibleError(
    PerformanceCompensationError
):
    """Raised when shadow entitlement cannot be established."""


def _require_canonical_id(name: str, value: str) -> None:
    if not value or value != value.strip():
        raise ValueError(
            f"{name} is required and must be canonical"
        )


def _require_canonical_currency(currency: str) -> None:
    if (
        not currency
        or currency != currency.strip()
        or currency != currency.upper()
    ):
        raise ValueError(
            "currency must be canonical uppercase text"
        )


def _require_finite_decimal(name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")

    if not value.is_finite():
        raise ValueError(f"{name} must be finite")

    return value


@dataclass(frozen=True, slots=True)
class PerformanceCompensationTerms:
    """
    Immutable commercial terms for shadow performance compensation.

    This object records whether a share of COM-002C new_economic_gain
    may later be treated as economically eligible for compensation.

    It does not collect a fee, raise a receivable, settle an invoice,
    deduct client funds, or grant execution authority.

    Settlement rounding is out of scope. There is no canonical
    monetary-rounding policy in the commercialization domain.
    """

    terms_id: str
    currency: str
    performance_compensation_rate: Decimal
    effective_from: str
    evidence_refs: Tuple[str, ...]
    accepted: bool
    effective_to: Optional[str] = None

    def __post_init__(self) -> None:
        _require_canonical_id("terms_id", self.terms_id)
        _require_canonical_currency(self.currency)

        rate = _require_finite_decimal(
            "performance_compensation_rate",
            self.performance_compensation_rate,
        )

        if rate < Decimal("0"):
            raise ValueError(
                "performance_compensation_rate cannot be negative"
            )

        if rate > Decimal("1"):
            raise ValueError(
                "performance_compensation_rate cannot exceed 1"
            )

        if not self.effective_from or self.effective_from != (
            self.effective_from.strip()
        ):
            raise ValueError(
                "effective_from is required and must be canonical"
            )

        if self.effective_to is not None and (
            not self.effective_to
            or self.effective_to != self.effective_to.strip()
        ):
            raise ValueError(
                "effective_to must be canonical when provided"
            )

        if not self.evidence_refs:
            raise ValueError(
                "compensation terms require evidence"
            )

        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be bool")

    @property
    def real_fee_collection_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def automatic_debit_allowed(self) -> bool:
        return False

    @property
    def invoice_settlement_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ShadowCompensationEntitlement:
    """
    Immutable shadow compensation entitlement for one accounting
    transition.

    The compensation base is transition.new_economic_gain only.
    Recovered losses and attributable realized P&L are never the
    compensation base.

    This object is not a bill, receivable, or collection instruction.
    """

    trade_id: str
    terms_id: str
    currency: str
    new_economic_gain: Decimal
    compensation_rate: Decimal
    shadow_compensation_amount: Decimal
    calculation_timestamp: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("trade_id", self.trade_id)
        _require_canonical_id("terms_id", self.terms_id)
        _require_canonical_currency(self.currency)

        gain = _require_finite_decimal(
            "new_economic_gain",
            self.new_economic_gain,
        )
        rate = _require_finite_decimal(
            "compensation_rate",
            self.compensation_rate,
        )
        amount = _require_finite_decimal(
            "shadow_compensation_amount",
            self.shadow_compensation_amount,
        )

        if gain < Decimal("0"):
            raise ValueError("new_economic_gain cannot be negative")

        if rate < Decimal("0") or rate > Decimal("1"):
            raise ValueError("compensation_rate must be between 0 and 1")

        if amount < Decimal("0"):
            raise ValueError(
                "shadow_compensation_amount cannot be negative"
            )

        if not self.calculation_timestamp:
            raise ValueError("calculation_timestamp is required")

        if not self.evidence_refs:
            raise ValueError("entitlement requires evidence")

    @property
    def real_fee_collection_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def automatic_debit_allowed(self) -> bool:
        return False

    @property
    def invoice_settlement_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_shadow_compensation_entitlement(
    transition: PerformanceAccountingTransition,
    terms: PerformanceCompensationTerms,
    calculation_timestamp: str,
) -> ShadowCompensationEntitlement:
    """
    Fail-closed COM-002D shadow entitlement builder.

    Only transition.new_economic_gain may form the compensation base.
    Existing loss recovery is never compensated again.

    Exact Decimal arithmetic is preserved. Settlement rounding is
    out of scope.
    """

    if not isinstance(terms, PerformanceCompensationTerms):
        raise TypeError(
            "terms must be PerformanceCompensationTerms"
        )

    if not isinstance(
        transition,
        PerformanceAccountingTransition,
    ):
        raise TypeError(
            "transition must be PerformanceAccountingTransition"
        )

    if not terms.accepted:
        raise PerformanceCompensationIneligibleError(
            "compensation terms are not accepted"
        )

    gain = _require_finite_decimal(
        "new_economic_gain",
        transition.new_economic_gain,
    )

    if gain < Decimal("0"):
        raise PerformanceCompensationIneligibleError(
            "new_economic_gain cannot be negative"
        )

    transition_currency = transition.new_state.currency

    if terms.currency != transition_currency:
        raise PerformanceCompensationIneligibleError(
            "terms currency does not match transition currency"
        )

    if (
        transition.previous_state.currency
        != transition_currency
    ):
        raise PerformanceCompensationIneligibleError(
            "transition state currencies are inconsistent"
        )

    if not calculation_timestamp or calculation_timestamp != (
        calculation_timestamp.strip()
    ):
        raise ValueError(
            "calculation_timestamp is required and must be canonical"
        )

    amount = gain * terms.performance_compensation_rate

    if amount < Decimal("0"):
        raise PerformanceCompensationIneligibleError(
            "shadow compensation cannot be negative"
        )

    return ShadowCompensationEntitlement(
        trade_id=transition.trade_id,
        terms_id=terms.terms_id,
        currency=terms.currency,
        new_economic_gain=gain,
        compensation_rate=terms.performance_compensation_rate,
        shadow_compensation_amount=amount,
        calculation_timestamp=calculation_timestamp,
        evidence_refs=terms.evidence_refs,
    )
