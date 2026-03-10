from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from backend.security.transaction_governor import TransactionGovernor
from backend.security.audit_ledger import AuditLedger


@dataclass
class ExecutionResult:
    allowed: bool
    executed: bool
    reason: str


class ExecutionController:
    """
    CSS Institutional Execution Controller

    Controls whether an action is allowed to reach execution,
    whether it must wait for approval, and records audit events.
    """

    def __init__(self) -> None:
        self.governor = TransactionGovernor()
        self.audit = AuditLedger()

    def execute(
        self,
        user_id: str,
        role: str,
        action: str,
        payload: Dict[str, Any],
    ) -> ExecutionResult:
        decision = self.governor.process(user_id, role, action, payload)

        if not decision.allowed:
            self.audit.record(
                "execution_blocked",
                user_id,
                {
                    "action": action,
                    "reason": decision.reason,
                },
            )
            return ExecutionResult(
                allowed=False,
                executed=False,
                reason=decision.reason,
            )

        if decision.requires_approval:
            self.audit.record(
                "execution_pending_approval",
                user_id,
                {
                    "action": action,
                    "pending_action_id": decision.action_id,
                },
            )
            return ExecutionResult(
                allowed=True,
                executed=False,
                reason="Awaiting checker approval",
            )

        self.audit.record(
            "execution_performed",
            user_id,
            {
                "action": action,
                "payload": payload,
            },
        )
        return ExecutionResult(
            allowed=True,
            executed=True,
            reason="Execution successful",
        )