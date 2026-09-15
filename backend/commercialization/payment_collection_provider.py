from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol, Tuple

from backend.commercialization.production_charging_gate import (
    ProductionChargingAssessment,
)


class PaymentProviderStatus(str, Enum):
    DISABLED = "DISABLED"
    APPROVED = "APPROVED"


@dataclass(frozen=True, slots=True)
class PaymentProviderConfiguration:
    provider_id: str
    status: PaymentProviderStatus
    environment: str
    provider_account_reference: str | None
    approval_reference: str | None
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.provider_id or self.provider_id != self.provider_id.strip():
            raise ValueError("provider_id is required and must be canonical")
        if not self.environment or self.environment != self.environment.strip():
            raise ValueError("environment is required and must be canonical")
        if not isinstance(self.status, PaymentProviderStatus):
            raise TypeError("status must be PaymentProviderStatus")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("provider configuration requires evidence refs")
        if self.status == PaymentProviderStatus.APPROVED:
            if not self.provider_account_reference or not self.approval_reference:
                raise ValueError(
                    "approved provider requires account and approval references"
                )


@dataclass(frozen=True, slots=True)
class PaymentCollectionRequest:
    collection_id: str
    customer_id: str
    account_reference: str
    amount: Decimal
    currency: str
    idempotency_key: str
    invoice_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "collection_id",
            "customer_id",
            "account_reference",
            "idempotency_key",
            "invoice_reference",
        ):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise TypeError("amount must be a finite Decimal")
        if self.amount <= Decimal("0"):
            raise ValueError("amount must be positive")
        if not self.currency or self.currency != self.currency.strip() or self.currency != self.currency.upper():
            raise ValueError("currency must be canonical uppercase text")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("collection request requires evidence refs")


@dataclass(frozen=True, slots=True)
class PaymentCollectionPreflight:
    allowed: bool
    reason_codes: Tuple[str, ...]
    provider_id: str


def assess_payment_collection_preflight(
    *,
    charging_assessment: ProductionChargingAssessment,
    provider: PaymentProviderConfiguration,
) -> PaymentCollectionPreflight:
    if not isinstance(charging_assessment, ProductionChargingAssessment):
        raise TypeError("charging_assessment must be ProductionChargingAssessment")
    if not isinstance(provider, PaymentProviderConfiguration):
        raise TypeError("provider must be PaymentProviderConfiguration")

    reasons = []
    if not charging_assessment.allowed:
        reasons.append("PRODUCTION_CHARGING_GATE_BLOCKED")
        reasons.extend(
            f"CHARGING_GATE:{reason}"
            for reason in charging_assessment.reason_codes
        )
    if provider.status != PaymentProviderStatus.APPROVED:
        reasons.append("PAYMENT_PROVIDER_NOT_APPROVED")
    if provider.environment.lower() != "production":
        reasons.append("PAYMENT_PROVIDER_NOT_PRODUCTION_ENVIRONMENT")

    return PaymentCollectionPreflight(
        allowed=not reasons,
        reason_codes=tuple(reasons),
        provider_id=provider.provider_id,
    )


class PaymentCollectionProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    def collect(
        self,
        request: PaymentCollectionRequest,
        preflight: PaymentCollectionPreflight,
    ) -> str:
        ...


class DisabledPaymentCollectionProvider:
    """Default provider. Never moves money."""

    @property
    def provider_id(self) -> str:
        return "DISABLED"

    def collect(
        self,
        request: PaymentCollectionRequest,
        preflight: PaymentCollectionPreflight,
    ) -> str:
        if not isinstance(request, PaymentCollectionRequest):
            raise TypeError("request must be PaymentCollectionRequest")
        if not isinstance(preflight, PaymentCollectionPreflight):
            raise TypeError("preflight must be PaymentCollectionPreflight")
        raise RuntimeError("payment collection provider is disabled")
