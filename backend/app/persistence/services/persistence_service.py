from typing import Any

from backend.app.persistence.repositories.legal_acceptance_repository import (
    LegalAcceptanceRepository,
)
from backend.app.persistence.repositories.pnl_snapshot_repository import (
    PnlSnapshotRepository,
)
from backend.app.persistence.repositories.session_repository import (
    SessionRepository,
)
from backend.app.persistence.repositories.trade_repository import (
    TradeRepository,
)
from backend.app.persistence.migrations.runner import run_migrations


class PersistenceService:
    """
    Central persistence coordination service.

    This service provides a unified access layer
    for all CSS persistence repositories.

    IMPORTANT:
    - No orchestration logic here
    - No governance logic here
    - No broker execution logic here
    - Persistence only
    """

    def __init__(self) -> None:
        run_migrations()
        self.sessions = SessionRepository()
        self.trades = TradeRepository()
        self.pnl_snapshots = (
            PnlSnapshotRepository()
        )
        self.legal_acceptances = (
            LegalAcceptanceRepository()
        )

    def healthcheck(self) -> dict[str, Any]:
        """
        Basic persistence health verification.
        """

        return {
            "service": "PersistenceService",
            "status": "ok",
            "repositories": {
                "sessions": True,
                "trades": True,
                "pnl_snapshots": True,
                "legal_acceptances": True,
            },
        }
