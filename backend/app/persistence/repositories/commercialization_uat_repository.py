from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.commercialization_uat import (
    CommercializationUatResult,
)


class CommercializationUatRepository(BaseRepository):
    def create_result(self, result: CommercializationUatResult) -> None:
        self.execute(
            """
            INSERT INTO commercialization_uat_results (
                run_id, scenario, status, executed_at,
                environment_reference, evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                result.run_id,
                result.scenario.value,
                result.status.value,
                result.executed_at,
                result.environment_reference,
                json.dumps(list(result.evidence_refs), separators=(",", ":")),
            ),
        )

    def list_run(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT * FROM commercialization_uat_results
            WHERE run_id = ?
            ORDER BY scenario ASC, executed_at ASC, result_id ASC
            """,
            (run_id,),
        )
        return [dict(row) for row in rows]
