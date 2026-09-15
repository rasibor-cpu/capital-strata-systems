from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext, MAX_EMAX, MIN_EMIN, Inexact
from typing import Any, Optional, Tuple

from backend.commercialization.billing_profile import (
    _parse_canonical_utc_timestamp, _require_evidence_refs,
)
from backend.commercialization.final_fee_selection import FinalFeeBasis
from backend.commercialization.performance_compensation import (
    _require_canonical_currency, _require_canonical_id, _require_finite_decimal,
)
from backend.commercialization.performance_crystallization import CrystallizationStatus


class ClientEarningsSummaryError(ValueError):
    """Base client-earnings read-model contract error."""


class ClientEarningsSummaryUnavailableError(ClientEarningsSummaryError):
    """Raised when a canonical commercial source cannot support this projection."""


CLIENT_LANGUAGE_FEE_RULE = (
    "For CSS-attributable trading performance, your CSS charge is the agreed "
    "performance fee on qualifying new economic gain after loss recovery. "
    "A platform minimum does not override that amount."
)

CLIENT_LANGUAGE_FX_NOTE = (
    "Your performance fee was calculated in your trading currency and converted "
    "to USD using the approved rate shown below."
)

WITHDRAWABLE_FUNDS_NOTE = (
    "Withdrawal availability is determined by a separate advisory calculation "
    "and is not part of this earnings summary."
)


def _exact_product(amount: Decimal, rate: Decimal) -> Decimal:
    """Preserve all coefficient digits independently of caller precision."""
    with localcontext() as context:
        context.prec = len(amount.as_tuple().digits) + len(rate.as_tuple().digits)
        context.Emax = MAX_EMAX
        context.Emin = MIN_EMIN
        context.traps[Inexact] = True
        return amount * rate


@dataclass(frozen=True, slots=True)
class CommercialClientEarningsSummary:
    """Read-only client-facing earnings and charge-explainability projection.

    Composed entirely from already-persisted canonical commercialization
    records (COM-002B through COM-002X). This projection creates no
    economics of its own, and authorizes no invoice, receivable, ledger
    posting, tax calculation, settlement-currency conversion, or money
    movement. It is documentary presentation only.

    For a non-billable ``commercial_status`` (anything other than
    ``ELIGIBLE``), every fee/charge-related field is ``None``: nothing has
    been selected, invoiced, or recognized yet.
    """

    account_reference: str
    policy_id: str
    terms_id: str
    billing_period_start: str
    billing_period_end: str
    performance_currency: str
    billing_currency: str
    commercial_status: CrystallizationStatus

    realized_attributable_profit: Decimal
    recovered_loss: Decimal
    new_economic_gain: Decimal

    performance_fee_rate: Optional[Decimal]
    performance_fee_source_amount: Optional[Decimal]
    performance_fee_billing_currency_amount: Optional[Decimal]

    platform_access_fee_amount: Optional[Decimal]
    access_terms_id: Optional[str]

    selected_fee_basis: Optional[FinalFeeBasis]
    selected_fee_amount: Optional[Decimal]
    final_fee_selection_id: Optional[str]

    net_earnings_after_css_fee: Optional[Decimal]

    fx_rate: Optional[Decimal]
    fx_conversion_id: Optional[str]
    fx_rate_source_reference: Optional[str]

    invoice_id: Optional[str]
    receivable_id: Optional[str]

    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("account_reference", self.account_reference)
        _require_canonical_id("policy_id", self.policy_id)
        _require_canonical_id("terms_id", self.terms_id)
        _require_canonical_currency(self.performance_currency)
        _require_canonical_currency(self.billing_currency)

        start = _parse_canonical_utc_timestamp("billing_period_start", self.billing_period_start)
        end = _parse_canonical_utc_timestamp("billing_period_end", self.billing_period_end)
        if end <= start:
            raise ValueError("billing_period_end must be after billing_period_start")

        if not isinstance(self.commercial_status, CrystallizationStatus):
            raise TypeError("commercial_status must be CrystallizationStatus")

        for name in ("realized_attributable_profit", "recovered_loss", "new_economic_gain"):
            _require_finite_decimal(name, getattr(self, name))
        if self.recovered_loss < 0:
            raise ValueError("recovered_loss cannot be negative")
        if self.new_economic_gain < 0:
            raise ValueError("new_economic_gain cannot be negative")

        optional_decimal_fields = (
            "performance_fee_rate", "performance_fee_source_amount",
            "performance_fee_billing_currency_amount", "platform_access_fee_amount",
            "selected_fee_amount", "net_earnings_after_css_fee",
        )
        optional_id_fields = (
            "access_terms_id", "final_fee_selection_id", "fx_conversion_id",
            "fx_rate_source_reference", "invoice_id", "receivable_id",
        )

        is_billable = self.commercial_status == CrystallizationStatus.ELIGIBLE

        if is_billable:
            for name in optional_decimal_fields:
                _require_finite_decimal(name, getattr(self, name))
            for name in ("access_terms_id", "final_fee_selection_id"):
                _require_canonical_id(name, getattr(self, name))
            if not isinstance(self.selected_fee_basis, FinalFeeBasis):
                raise TypeError("selected_fee_basis must be FinalFeeBasis when billable")
            if self.performance_fee_rate < 0 or self.performance_fee_rate > 1:
                raise ValueError("performance_fee_rate must be between 0 and 1")
            for name in ("performance_fee_source_amount", "performance_fee_billing_currency_amount",
                         "platform_access_fee_amount", "selected_fee_amount"):
                if getattr(self, name) < 0:
                    raise ValueError(f"{name} cannot be negative")

            if self.performance_fee_billing_currency_amount <= Decimal("0"):
                raise ValueError(
                    "billable CSS-attributable performance must have a positive performance fee"
                )
            if self.selected_fee_amount != self.performance_fee_billing_currency_amount:
                raise ValueError(
                    "selected_fee_amount must equal the performance fee on qualifying CSS gains"
                )
            if self.selected_fee_basis != FinalFeeBasis.PERFORMANCE_COMPENSATION:
                raise ValueError(
                    "CSS-attributable performance cannot use platform-minimum fee selection"
                )

            if self.performance_currency == self.billing_currency:
                if self.fx_rate is not None or self.fx_conversion_id is not None:
                    raise ValueError("USD performance must bypass FX evidence")
                if self.performance_fee_source_amount != self.performance_fee_billing_currency_amount:
                    raise ValueError("USD performance amount must be preserved exactly")
            else:
                _require_canonical_id("fx_conversion_id", self.fx_conversion_id)
                _require_finite_decimal("fx_rate", self.fx_rate)
                if self.fx_rate <= 0:
                    raise ValueError("fx_rate must be positive")
                if self.performance_fee_billing_currency_amount != _exact_product(
                    self.performance_fee_source_amount, self.fx_rate,
                ):
                    raise ValueError("performance_fee_billing_currency_amount must equal source * fx_rate exactly")

            normalized_realized_profit = (
                self.realized_attributable_profit
                if self.performance_currency == self.billing_currency
                else _exact_product(self.realized_attributable_profit, self.fx_rate)
            )
            if self.net_earnings_after_css_fee != normalized_realized_profit - self.selected_fee_amount:
                raise ValueError(
                    "net_earnings_after_css_fee must equal normalized realized profit "
                    "less the selected fee, exactly"
                )
        else:
            for name in optional_decimal_fields:
                if getattr(self, name) is not None:
                    raise ValueError(f"{name} must be None for a non-billable period")
            for name in optional_id_fields:
                if getattr(self, name) is not None:
                    raise ValueError(f"{name} must be None for a non-billable period")
            if self.selected_fee_basis is not None:
                raise ValueError("selected_fee_basis must be None for a non-billable period")
            if self.fx_rate is not None:
                raise ValueError("fx_rate must be None for a non-billable period")

        if self.invoice_id is not None:
            _require_canonical_id("invoice_id", self.invoice_id)
        if self.receivable_id is not None:
            _require_canonical_id("receivable_id", self.receivable_id)
            if self.invoice_id is None:
                raise ValueError("receivable_id requires invoice_id")

        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be an immutable tuple")
        _require_evidence_refs(self.evidence_refs)

    @property
    def is_billable_period(self) -> bool:
        return self.commercial_status == CrystallizationStatus.ELIGIBLE

    @property
    def fee_rule_language(self) -> str:
        return CLIENT_LANGUAGE_FEE_RULE

    @property
    def fx_language(self) -> Optional[str]:
        return CLIENT_LANGUAGE_FX_NOTE if self.fx_conversion_id else None

    @property
    def withdrawable_funds_note(self) -> str:
        return WITHDRAWABLE_FUNDS_NOTE

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def broker_withdrawal_allowed(self) -> bool:
        return False

    @property
    def payment_execution_allowed(self) -> bool:
        return False

    @property
    def tax_calculation_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def settlement_currency_conversion_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False

    def explain(self) -> dict[str, Any]:
        """Deterministic, structured calculation explanation (A-E). No hidden arithmetic."""

        performance_result = {
            "css_attributable_realized_profit": str(self.realized_attributable_profit),
            "recovered_loss": str(self.recovered_loss),
            "new_economic_gain": str(self.new_economic_gain),
            "currency": self.performance_currency,
        }

        performance_compensation = None
        platform_minimum = None
        final_charge = None
        net_economics = None

        if self.is_billable_period:
            performance_compensation = {
                "agreed_rate": str(self.performance_fee_rate),
                "source_amount": str(self.performance_fee_source_amount),
                "source_currency": self.performance_currency,
                "billing_currency_amount": str(self.performance_fee_billing_currency_amount),
                "billing_currency": self.billing_currency,
                "fx_rate": str(self.fx_rate) if self.fx_rate is not None else None,
                "fx_conversion_id": self.fx_conversion_id,
                "fx_rate_source_reference": self.fx_rate_source_reference,
                "language": self.fx_language,
            }
            platform_minimum = {
                "platform_access_fee_amount": str(self.platform_access_fee_amount),
                "access_terms_id": self.access_terms_id,
                "billing_currency": self.billing_currency,
            }
            final_charge = {
                "platform_access_reference_amount": str(self.platform_access_fee_amount),
                "performance_fee_amount": str(self.performance_fee_billing_currency_amount),
                "selected_fee_basis": self.selected_fee_basis.value,
                "selected_fee_amount": str(self.selected_fee_amount),
                "platform_minimum_overrides_performance_fee": False,
                "customer_pays_both": False,
                "client_language": self.fee_rule_language,
            }
            net_economics = {
                "net_earnings_after_css_fee": str(self.net_earnings_after_css_fee),
                "currency": self.billing_currency,
            }

        return {
            "commercial_status": self.commercial_status.value,
            "A_performance_result": performance_result,
            "B_performance_compensation": performance_compensation,
            "C_platform_minimum": platform_minimum,
            "D_final_charge": final_charge,
            "E_net_economics": net_economics,
            "withdrawable_funds_note": self.withdrawable_funds_note,
        }
