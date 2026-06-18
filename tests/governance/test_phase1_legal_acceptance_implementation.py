from datetime import UTC, datetime

from backend.app.compliance.legal_acceptance import (
    AcceptanceBlockReason,
    AcceptanceValidationStatus,
)
from backend.app.compliance.legal_acceptance_enforcement import (
    AcceptanceEnforcementStatus,
    TradingSessionReadinessRequest,
    enforce_trading_session_acceptance,
)
from backend.app.compliance.legal_acceptance_service import LegalAcceptanceService
from backend.app.compliance.legal_acceptance_store import InMemoryLegalAcceptanceStore
from backend.app.compliance.legal_acceptance_versions import (
    LEGAL_TERMS,
    LEGAL_TERMS_CURRENT_VERSION,
    TRADING_RISK_DISCLOSURE,
    TRADING_RISK_DISCLOSURE_CURRENT_VERSION,
)


def build_service() -> LegalAcceptanceService:
    return LegalAcceptanceService(store=InMemoryLegalAcceptanceStore())


def record_current_pair(service: LegalAcceptanceService, user_id: str) -> None:
    service.record_current_acceptance(
        user_id=user_id,
        acceptance_type=LEGAL_TERMS,
        accepted_at=datetime(2026, 6, 4, tzinfo=UTC),
        audit_reference="audit://legal/current",
    )
    service.record_current_acceptance(
        user_id=user_id,
        acceptance_type=TRADING_RISK_DISCLOSURE,
        accepted_at=datetime(2026, 6, 4, tzinfo=UTC),
        audit_reference="audit://risk/current",
    )


def test_missing_acceptance_blocks() -> None:
    service = build_service()

    result = service.validate_acceptance(
        user_id="user1",
        acceptance_type=LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.BLOCK
    assert result.block_reason == AcceptanceBlockReason.MISSING_ACCEPTANCE


def test_invalid_acceptance_blocks() -> None:
    service = build_service()

    service.record_acceptance(
        user_id="user1",
        acceptance_type=LEGAL_TERMS,
        acceptance_version=LEGAL_TERMS_CURRENT_VERSION,
        accepted=False,
        accepted_at=datetime(2026, 6, 4, tzinfo=UTC),
        audit_reference="audit://legal/declined",
    )

    result = service.validate_acceptance(
        user_id="user1",
        acceptance_type=LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.BLOCK
    assert result.block_reason == AcceptanceBlockReason.INVALID_ACCEPTANCE


def test_outdated_acceptance_blocks() -> None:
    service = build_service()

    service.record_acceptance(
        user_id="user1",
        acceptance_type=LEGAL_TERMS,
        acceptance_version="old_version",
        accepted=True,
        accepted_at=datetime(2026, 6, 4, tzinfo=UTC),
        audit_reference="audit://legal/old",
    )

    result = service.validate_acceptance(
        user_id="user1",
        acceptance_type=LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.BLOCK
    assert result.block_reason == AcceptanceBlockReason.OUTDATED_ACCEPTANCE


def test_current_acceptance_allows() -> None:
    service = build_service()

    service.record_current_acceptance(
        user_id="user1",
        acceptance_type=LEGAL_TERMS,
        accepted_at=datetime(2026, 6, 4, tzinfo=UTC),
        audit_reference="audit://legal/current",
    )

    result = service.validate_acceptance(
        user_id="user1",
        acceptance_type=LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.ALLOW
    assert result.block_reason is None


def test_all_required_acceptances() -> None:
    service = build_service()
    record_current_pair(service, "user1")

    aggregate = service.validate_required_acceptances(
        user_id="user1",
    )

    assert aggregate.allowed is True
    assert aggregate.blocked is False


def test_enforcement_blocks_missing_acceptance() -> None:
    service = build_service()

    decision = enforce_trading_session_acceptance(
        request=TradingSessionReadinessRequest(
            user_id="user1",
            mode="PAPER",
        ),
        acceptance_service=service,
    )

    assert decision.status == AcceptanceEnforcementStatus.BLOCK
    assert decision.blocked is True


def test_enforcement_allows_current_acceptances() -> None:
    service = build_service()
    record_current_pair(service, "user1")

    decision = enforce_trading_session_acceptance(
        request=TradingSessionReadinessRequest(
            user_id="user1",
            mode="PAPER",
        ),
        acceptance_service=service,
    )

    assert decision.status == AcceptanceEnforcementStatus.ALLOW
    assert decision.allowed is True


def test_non_trading_readiness_does_not_grant_trading_authority() -> None:
    service = build_service()

    decision = enforce_trading_session_acceptance(
        request=TradingSessionReadinessRequest(
            user_id="user1",
            mode="REPORTING",
            source="dashboard",
            override_claims={"force_trading_ready": True},
        ),
        acceptance_service=service,
    )

    assert decision.status == AcceptanceEnforcementStatus.ALLOW
    assert decision.trading_enabled is False
    assert decision.validation is None