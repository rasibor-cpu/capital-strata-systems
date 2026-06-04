from datetime import datetime

from backend.app.compliance.legal_acceptance import (
    AcceptanceBlockReason,
    AcceptanceValidationStatus,
    LegalAcceptanceRecord,
)

from backend.app.compliance.legal_acceptance_service import (
    LegalAcceptanceService,
)

from backend.app.compliance.legal_acceptance_store import (
    InMemoryLegalAcceptanceStore,
)

from backend.app.compliance.legal_acceptance_versions import (
    LEGAL_TERMS,
    LEGAL_TERMS_CURRENT_VERSION,
    TRADING_RISK_DISCLOSURE,
    TRADING_RISK_DISCLOSURE_CURRENT_VERSION,
)


def build_service():
    return LegalAcceptanceService(
        store=InMemoryLegalAcceptanceStore()
    )


def test_missing_acceptance_blocks():
    service = build_service()

    result = service.validate_acceptance(
        "user1",
        LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.BLOCK
    assert result.reason == AcceptanceBlockReason.MISSING_ACCEPTANCE


def test_invalid_acceptance_blocks():
    service = build_service()

    service.store.save(
        LegalAcceptanceRecord(
            user_id="user1",
            acceptance_type=LEGAL_TERMS,
            acceptance_version=LEGAL_TERMS_CURRENT_VERSION,
            accepted=False,
            accepted_at=datetime.utcnow(),
            audit_reference="audit1",
        )
    )

    result = service.validate_acceptance(
        "user1",
        LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.BLOCK
    assert result.reason == AcceptanceBlockReason.INVALID_ACCEPTANCE


def test_outdated_acceptance_blocks():
    service = build_service()

    service.store.save(
        LegalAcceptanceRecord(
            user_id="user1",
            acceptance_type=LEGAL_TERMS,
            acceptance_version="old_version",
            accepted=True,
            accepted_at=datetime.utcnow(),
            audit_reference="audit2",
        )
    )

    result = service.validate_acceptance(
        "user1",
        LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.BLOCK
    assert result.reason == AcceptanceBlockReason.OUTDATED_ACCEPTANCE


def test_current_acceptance_allows():
    service = build_service()

    service.store.save(
        LegalAcceptanceRecord(
            user_id="user1",
            acceptance_type=LEGAL_TERMS,
            acceptance_version=LEGAL_TERMS_CURRENT_VERSION,
            accepted=True,
            accepted_at=datetime.utcnow(),
            audit_reference="audit3",
        )
    )

    result = service.validate_acceptance(
        "user1",
        LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.ALLOW


def test_all_required_acceptances():
    service = build_service()

    service.store.save(
        LegalAcceptanceRecord(
            user_id="user1",
            acceptance_type=LEGAL_TERMS,
            acceptance_version=LEGAL_TERMS_CURRENT_VERSION,
            accepted=True,
            accepted_at=datetime.utcnow(),
            audit_reference="audit4",
        )
    )

    service.store.save(
        LegalAcceptanceRecord(
            user_id="user1",
            acceptance_type=TRADING_RISK_DISCLOSURE,
            acceptance_version=TRADING_RISK_DISCLOSURE_CURRENT_VERSION,
            accepted=True,
            accepted_at=datetime.utcnow(),
            audit_reference="audit5",
        )
    )

    result = service.validate_required_acceptances(
        "user1"
    )

    assert result.status == AcceptanceValidationStatus.ALLOW