from __future__ import annotations

import json
from typing import Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.production_charging_assessment_service import (
    ProductionChargingAssessmentService,
)
from backend.commercialization.payment_collection_provider import (
    PaymentCollectionPreflight,
    PaymentProviderConfiguration,
    PaymentProviderStatus,
    assess_payment_collection_preflight,
)


class PaymentCollectionPreflightService:
    """Read-only preflight. Never invokes a payment provider."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def assess(
        self,
        *,
        provider_id: str,
        customer_id: str,
        account_reference: str,
        agreement_id: str,
        agreement_version: str,
        jurisdiction_code: str,
        assessed_at: str,
    ) -> PaymentCollectionPreflight:
        row = (
            self._service.production_infrastructure
            .get_payment_provider_configuration(provider_id)
        )
        if row is None:
            return PaymentCollectionPreflight(
                allowed=False,
                reason_codes=("PAYMENT_PROVIDER_CONFIGURATION_MISSING",),
                provider_id=provider_id,
            )

        provider = PaymentProviderConfiguration(
            provider_id=row["provider_id"],
            status=PaymentProviderStatus(row["status"]),
            environment=row["environment"],
            provider_account_reference=row["provider_account_reference"],
            approval_reference=row["approval_reference"],
            evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
        )
        charging = ProductionChargingAssessmentService(self._service).assess(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            assessed_at=assessed_at,
        )
        return assess_payment_collection_preflight(
            charging_assessment=charging,
            provider=provider,
        )
