"""
Position Concurrency Guard
---------------------------
Prevents new trades if maximum concurrent open positions
would be exceeded.
"""

from dataclasses import dataclass
from enum import Enum


class PositionDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass
class PositionPolicy:
    max_concurrent_positions: int = 20


@dataclass
class PositionState:
    open_positions: int


class PositionGuard:
    def __init__(self, policy: PositionPolicy):
        self.policy = policy

    def evaluate(self, state: PositionState):
        if state.open_positions >= self.policy.max_concurrent_positions:
            return {
                "decision": PositionDecision.BLOCK,
                "reason": "Max concurrent positions reached",
                "open_positions": state.open_positions,
                "max_allowed": self.policy.max_concurrent_positions,
            }

        return {
            "decision": PositionDecision.ALLOW,
            "reason": "Within position limits",
            "open_positions": state.open_positions,
            "max_allowed": self.policy.max_concurrent_positions,
        }
