"""
Execution Journal
=================

Purpose:
- Persist a full, ordered execution audit trail
- Gracefully degrade if audit store is unavailable
- NEVER block execution due to logging failures
"""

from __future__ import annotations

from typing import Dict, Any

try:
    # Audit store may be ignored by git or missing in some envs
    from engine.audit.audit_store import AuditStore
except Exception:  # pragma: no cover
    AuditStore = None  # type: ignore


class ExecutionJournal:
    """
    Writes execution-related audit records in order.
    """

    def __init__(self) -> None:
        self._store = AuditStore() if AuditStore else None

    def _safe_write(
        self,
        *,
        engine_run_id: str,
        record_type: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        Write audit record without ever raising.
        """
        if not self._store:
            return
        try:
            self._store.write(
                engine_run_id=engine_run_id,
                record_type=record_type,
                payload=payload,
            )
        except Exception:
            # Audit must NEVER block trading logic
            return

    def record(
        self,
        *,
        engine_run_id: str,
        decision_envelope: Dict[str, Any],
        firewall_result: Dict[str, Any],
        execution_request: Dict[str, Any],
        execution_result: Dict[str, Any] | None,
    ) -> None:
        """
        Record a complete execution lifecycle.
        """

        self._safe_write(
            engine_run_id=engine_run_id,
            record_type="decision_envelope",
            payload=decision_envelope,
        )

        self._safe_write(
            engine_run_id=engine_run_id,
            record_type="firewall_result",
            payload=firewall_result,
        )

        self._safe_write(
            engine_run_id=engine_run_id,
            record_type="execution_request",
            payload=execution_request,
        )

        if execution_result is not None:
            self._safe_write(
                engine_run_id=engine_run_id,
                record_type="execution_result",
                payload=execution_result,
            )
