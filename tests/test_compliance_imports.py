import subprocess
import sys
from pathlib import Path

from backend.app.compliance.legal_acceptance import (
    AcceptanceBlockReason,
    AcceptanceValidationStatus,
)
from backend.app.compliance.legal_acceptance_service import LegalAcceptanceService
from backend.app.compliance.legal_acceptance_store import InMemoryLegalAcceptanceStore
from backend.app.compliance.legal_acceptance_versions import LEGAL_TERMS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _assert_fresh_import_succeeds(statement: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", statement],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_compliance_package_repository_export_imports_cleanly() -> None:
    _assert_fresh_import_succeeds(
        "from backend.app.compliance import "
        "LegalAcceptanceRepository, LegalAcceptanceService; "
        "print(LegalAcceptanceRepository.__name__, LegalAcceptanceService.__name__)"
    )


def test_repository_then_compliance_package_imports_cleanly() -> None:
    _assert_fresh_import_succeeds(
        "from backend.app.persistence.repositories.legal_acceptance_repository "
        "import LegalAcceptanceRepository; "
        "from backend.app.compliance import LegalAcceptanceService; "
        "print(LegalAcceptanceRepository.__name__, LegalAcceptanceService.__name__)"
    )


def test_persistence_service_then_compliance_repository_export_imports_cleanly() -> None:
    _assert_fresh_import_succeeds(
        "from backend.app.persistence.services.persistence_service "
        "import PersistenceService; "
        "from backend.app.compliance import LegalAcceptanceRepository; "
        "print(PersistenceService.__name__, LegalAcceptanceRepository.__name__)"
    )


def test_compliance_star_import_preserves_public_repository_export() -> None:
    _assert_fresh_import_succeeds(
        "namespace = {}; "
        "exec('from backend.app.compliance import *', namespace); "
        "print(namespace['LegalAcceptanceRepository'].__name__)"
    )


def test_trade_decision_orchestrator_imports_without_compliance_cycle() -> None:
    _assert_fresh_import_succeeds(
        "from backend.intelligence.trade_decision_orchestrator "
        "import TradeDecisionOrchestrator; "
        "print(TradeDecisionOrchestrator.__name__)"
    )


def test_legal_acceptance_behavior_remains_fail_closed() -> None:
    service = LegalAcceptanceService(store=InMemoryLegalAcceptanceStore())

    result = service.validate_acceptance(
        user_id="user-without-acceptance",
        acceptance_type=LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.BLOCK
    assert result.block_reason == AcceptanceBlockReason.MISSING_ACCEPTANCE
