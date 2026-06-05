from dataclasses import dataclass
from datetime import UTC, datetime

from backend.app.compliance.legal_acceptance import (
    AcceptanceBlockReason,
    AcceptanceValidationResult,
    AcceptanceValidationStatus,
    LegalAcceptanceRecord,
    validate_acceptance_record_shape,
)
from backend.app.compliance.legal_acceptance_store import LegalAcceptanceStore
from backend.app.compliance.legal_acceptance_versions import (
    CURRENT_ACCEPTANCE_VERSIONS,
    REQUIRED_ACCEPTANCE_TYPES,
    current_version_for,
    is_supported_acceptance_type,
)


@dataclass(frozen=True)
class RequiredAcceptanceValidation:
    user_id: str
    results: dict[str, AcceptanceValidationResult]

    @property
    def allowed(self) -> bool:
        return all(result.allowed for result in self.results.values())

    @property
    def blocked(self) -> bool:
        return not self.allowed

    @property
    def blocking_results(self) -> tuple[AcceptanceValidationResult, ...]:
        return tuple(result for result in self.results.values() if result.blocked)


class LegalAcceptanceService:
    def __init__(self, store: LegalAcceptanceStore | None = None) -> None:
        if store is None:
            from backend.app.persistence.repositories.legal_acceptance_repository import (
                LegalAcceptanceRepository,
            )

            store = LegalAcceptanceRepository()

        self._store = store
        self.store = store

    def record_acceptance(
        self,
        *,
        user_id: str,
        acceptance_type: str,
        acceptance_version: str,
        accepted: bool,
        audit_reference: str,
        accepted_at: datetime | None = None,
    ) -> LegalAcceptanceRecord:
        if not is_supported_acceptance_type(acceptance_type):
            raise ValueError(f"Unsupported acceptance type: {acceptance_type}")

        record = LegalAcceptanceRecord(
            user_id=user_id,
            acceptance_type=acceptance_type,
            acceptance_version=acceptance_version,
            accepted=accepted,
            accepted_at=accepted_at or datetime.now(UTC),
            audit_reference=audit_reference,
        )

        return self._store.save(record)

    def record_current_acceptance(
        self,
        *,
        user_id: str,
        acceptance_type: str,
        audit_reference: str,
        accepted_at: datetime | None = None,
    ) -> LegalAcceptanceRecord:
        return self.record_acceptance(
            user_id=user_id,
            acceptance_type=acceptance_type,
            acceptance_version=current_version_for(acceptance_type),
            accepted=True,
            accepted_at=accepted_at,
            audit_reference=audit_reference,
        )

    def validate_acceptance(
        self,
        *,
        user_id: str,
        acceptance_type: str,
    ) -> AcceptanceValidationResult:
        required_version = (
            CURRENT_ACCEPTANCE_VERSIONS.get(acceptance_type)
            if is_supported_acceptance_type(acceptance_type)
            else None
        )

        if required_version is None:
            return AcceptanceValidationResult(
                status=AcceptanceValidationStatus.BLOCK,
                acceptance_type=acceptance_type,
                required_version=None,
                record=None,
                block_reason=AcceptanceBlockReason.INVALID_ACCEPTANCE,
                message=f"Unsupported acceptance type: {acceptance_type}",
            )

        try:
            record = self._store.latest_for(user_id, acceptance_type)
        except Exception as exc:
            return AcceptanceValidationResult(
                status=AcceptanceValidationStatus.BLOCK,
                acceptance_type=acceptance_type,
                required_version=required_version,
                record=None,
                block_reason=AcceptanceBlockReason.INVALID_ACCEPTANCE,
                message=(
                    f"Acceptance persistence unavailable or corrupt for "
                    f"{acceptance_type}: {type(exc).__name__}"
                ),
            )

        if record is None:
            return AcceptanceValidationResult(
                status=AcceptanceValidationStatus.BLOCK,
                acceptance_type=acceptance_type,
                required_version=required_version,
                record=None,
                block_reason=AcceptanceBlockReason.MISSING_ACCEPTANCE,
                message=(
                    f"Missing required acceptance for {acceptance_type} "
                    f"version {required_version}"
                ),
            )

        if not validate_acceptance_record_shape(record):
            return AcceptanceValidationResult(
                status=AcceptanceValidationStatus.BLOCK,
                acceptance_type=acceptance_type,
                required_version=required_version,
                record=record,
                block_reason=AcceptanceBlockReason.INVALID_ACCEPTANCE,
                message=f"Invalid acceptance for {acceptance_type}",
            )

        if record.acceptance_version != required_version:
            return AcceptanceValidationResult(
                status=AcceptanceValidationStatus.BLOCK,
                acceptance_type=acceptance_type,
                required_version=required_version,
                record=record,
                block_reason=AcceptanceBlockReason.OUTDATED_ACCEPTANCE,
                message=(
                    f"Outdated acceptance for {acceptance_type}: "
                    f"accepted {record.acceptance_version}, "
                    f"required {required_version}"
                ),
            )

        return AcceptanceValidationResult(
            status=AcceptanceValidationStatus.ALLOW,
            acceptance_type=acceptance_type,
            required_version=required_version,
            record=record,
            block_reason=None,
            message=f"Current valid acceptance found for {acceptance_type}",
        )

    def validate_required_acceptances(
        self,
        *,
        user_id: str,
    ) -> RequiredAcceptanceValidation:
        results = {
            acceptance_type: self.validate_acceptance(
                user_id=user_id,
                acceptance_type=acceptance_type,
            )
            for acceptance_type in REQUIRED_ACCEPTANCE_TYPES
        }

        return RequiredAcceptanceValidation(
            user_id=user_id,
            results=results,
        )