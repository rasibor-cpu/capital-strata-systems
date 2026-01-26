from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class EventRiskLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    HIGH = "HIGH"


@dataclass(frozen=True)
class EventRisk:
    """
    Represents an external macro / political risk signal.

    This module NEVER predicts price direction.
    It only answers: is it safe to trade right now?
    """
    level: EventRiskLevel
    reasons: List[str]
    as_of_utc: datetime


@dataclass
class EventPolicy:
    """
    Event blocking policy.

    high_risk_blocks:
      - If True, HIGH event risk will BLOCK trading
      - LOW risk never blocks (advisory only)
    """
    high_risk_blocks: bool = True


class EventRiskProvider:
    """
    Abstract provider interface.

    In the future this will:
    - pull economic calendar events
    - ingest geopolitical alerts
    - read curated risk feeds

    For now it is intentionally manual / stubbed.
    """

    def get_current_risk(self, as_of_utc: datetime) -> EventRisk:
        """
        Override this method when wiring real data.

        Default behaviour:
        - No blocking risk
        """
        return EventRisk(
            level=EventRiskLevel.NONE,
            reasons=[],
            as_of_utc=as_of_utc
        )


class EventGate:
    """
    Evaluates macro / political risk.
    Can only BLOCK trading — never ALLOW on its own.
    """

    def __init__(
        self,
        provider: Optional[EventRiskProvider] = None,
        policy: Optional[EventPolicy] = None,
    ):
        self.provider = provider or EventRiskProvider()
        self.policy = policy or EventPolicy()

    def evaluate(self, as_of_utc: datetime) -> Optional[str]:
        """
        Returns:
          - None if no blocking event risk
          - String reason if trading should be BLOCKED
        """
        risk = self.provider.get_current_risk(as_of_utc)

        if risk.level == EventRiskLevel.HIGH and self.policy.high_risk_blocks:
            joined = "; ".join(risk.reasons) if risk.reasons else "High macro/political risk event."
            return joined

        return None
