from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from backend.commercialization.payment_collection_provider import (
    PaymentCollectionPreflight,
    PaymentCollectionRequest,
)


@dataclass(frozen=True, slots=True)
class SandboxPaymentReceipt:
    provider_id: str
    collection_id: str
    provider_transaction_id: str
    idempotency_key: str
    status: str


class SandboxPaymentCollectionProvider:
    """Deterministic non-production payment simulator.

    This provider never connects to a network or external payment system.
    It exists only for full-test/UAT exercises.
    """

    def __init__(self) -> None:
        self._receipts_by_idempotency: Dict[str, SandboxPaymentReceipt] = {}

    @property
    def provider_id(self) -> str:
        return "CSS-SANDBOX-PAYMENTS"

    def collect(
        self,
        request: PaymentCollectionRequest,
        preflight: PaymentCollectionPreflight,
    ) -> str:
        if not isinstance(request, PaymentCollectionRequest):
            raise TypeError("request must be PaymentCollectionRequest")
        if not isinstance(preflight, PaymentCollectionPreflight):
            raise TypeError("preflight must be PaymentCollectionPreflight")
        if not preflight.allowed:
            raise RuntimeError("sandbox payment preflight is not allowed")
        if preflight.provider_id != self.provider_id:
            raise RuntimeError("sandbox payment provider identity mismatch")

        existing = self._receipts_by_idempotency.get(request.idempotency_key)
        if existing is not None:
            if existing.collection_id != request.collection_id:
                raise RuntimeError("idempotency key reused for another collection")
            return existing.provider_transaction_id

        transaction_id = f"sandbox-pay:{request.collection_id}"
        receipt = SandboxPaymentReceipt(
            provider_id=self.provider_id,
            collection_id=request.collection_id,
            provider_transaction_id=transaction_id,
            idempotency_key=request.idempotency_key,
            status="SIMULATED_SUCCEEDED",
        )
        self._receipts_by_idempotency[request.idempotency_key] = receipt
        return transaction_id

    def receipt_for(
        self,
        idempotency_key: str,
    ) -> SandboxPaymentReceipt | None:
        return self._receipts_by_idempotency.get(idempotency_key)


def build_sandbox_payment_preflight() -> PaymentCollectionPreflight:
    """Create test-only preflight for the deterministic sandbox adapter."""
    import os

    if os.getenv("CSS_FULL_TEST_MODE") != "1":
        raise RuntimeError(
            "sandbox payment preflight requires CSS_FULL_TEST_MODE=1"
        )
    return PaymentCollectionPreflight(
        allowed=True,
        reason_codes=("TEST_ONLY:SANDBOX_PREFLIGHT",),
        provider_id="CSS-SANDBOX-PAYMENTS",
    )
