from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import uuid
import time


@dataclass
class PendingAction:
    action_id: str
    action_type: str
    maker_user: str
    payload: dict
    timestamp: float
    approved: bool = False
    checker_user: str | None = None


class MakerCheckerEngine:
    """
    CSS Institutional Maker-Checker Governance Engine
    """

    def __init__(self) -> None:
        self.pending_actions: Dict[str, PendingAction] = {}

        # actions that require dual approval
        self.protected_actions = {
            "create_user",
            "large_transfer",
            "approve_trade",
            "system_override",
        }

    # -----------------------------------------------------

    def requires_checker(self, action: str) -> bool:
        return action in self.protected_actions

    # -----------------------------------------------------

    def submit_action(self, maker_user: str, action_type: str, payload: dict) -> str:

        action_id = str(uuid.uuid4())[:12]

        action = PendingAction(
            action_id=action_id,
            action_type=action_type,
            maker_user=maker_user,
            payload=payload,
            timestamp=time.time(),
        )

        self.pending_actions[action_id] = action

        return action_id

    # -----------------------------------------------------

    def list_pending(self) -> List[PendingAction]:
        return [a for a in self.pending_actions.values() if not a.approved]

    # -----------------------------------------------------

    def approve(self, checker_user: str, action_id: str) -> bool:

        if action_id not in self.pending_actions:
            return False

        action = self.pending_actions[action_id]

        if action.maker_user == checker_user:
            # maker cannot approve own action
            return False

        action.approved = True
        action.checker_user = checker_user

        return True

    # -----------------------------------------------------

    def get_action(self, action_id: str) -> PendingAction | None:
        return self.pending_actions.get(action_id)