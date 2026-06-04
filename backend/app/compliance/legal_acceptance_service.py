"""Phase 1 Legal & Trading-Risk Acceptance validation authority."""

from backend.app.compliance.legal_acceptance import (
    AcceptanceBlockReason,
    AcceptanceValidationResult,
    AcceptanceValidationStatus,
)

from backend.app.compliance.legal_acceptance_store import (
    InMemoryLegalAcceptanceStore,
)

from backend.app.compliance.legal_acceptance_versions import (
    CURRENT_ACCEPTANCE_VERSIONS,
    REQUIRED_ACCEPTANCE_TYPES,
)


class LegalAcceptanceService:
    """Validation authority for Phase 1 legal acceptance."""

    def __init__(
        self,
        store: InMemoryLegalAcceptanceStore,
    ) -> None:
        self.store = store

    def validate_acceptance(
        self,
        user_id: str,
        acceptance_type: str,
    ) -> AcceptanceValidationResult:

        record = self.store.get(
            user_id,
            acceptance_type,
        )

        if record is None:
            return AcceptanceValidationResult(
                status=AcceptanceValidationStatus.BLOCK,
                reason=AcceptanceBlockReason.MISSING_ACCEPTANCE,
            )

        if not record.accepted:
            return AcceptanceValidationResult(
                status=AcceptanceValidationStatus.BLOCK,
                reason=AcceptanceBlockReason.INVALID_ACCEPTANCE,
            )

        current_version = CURRENT_ACCEPTANCE_VERSIONS.get(
            acceptance_type
        )

        if record.acceptance_version != current_version:
            return AcceptanceValidationResult(
                status=AcceptanceValidationStatus.BLOCK,
                reason=AcceptanceBlockReason.OUTDATED_ACCEPTANCE,
            )

        return AcceptanceValidationResult(
            status=AcceptanceValidationStatus.ALLOW,
            reason=AcceptanceBlockReason.NONE,
        )

    def validate_required_acceptances(
        self,
        user_id: str,
    ) -> AcceptanceValidationResult:

        for acceptance_type in REQUIRED_ACCEPTANCE_TYPES:
            result = self.validate_acceptance(
                user_id=user_id,
                acceptance_type=acceptance_type,
            )

            if not result.allowed:
                return result

        return AcceptanceValidationResult(
            status=AcceptanceValidationStatus.ALLOW,
            reason=AcceptanceBlockReason.NONE,
        )