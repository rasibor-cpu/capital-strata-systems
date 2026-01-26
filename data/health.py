from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple

from .models import FeedStatus, DataIssue


@dataclass
class HealthPolicy:
    """
    SAFE MODE + auto-resume rule:
    - Enter SAFE MODE on any detected issue
    - Resume eligibility automatically after N consecutive clean minutes
    """
    required_clean_minutes_to_resume: int = 2


class FeedHealthManager:
    def __init__(self, policy: HealthPolicy):
        self.policy = policy
        self.status = FeedStatus(safe_mode=True)

    def mark_issue(self, issue: DataIssue) -> None:
        """
        Called when any data integrity issue is detected.
        Immediately engages SAFE MODE and resets the clean streak.
        """
        self.status.safe_mode = True
        self.status.last_issue = issue
        self.status.clean_streak_minutes = 0

    def mark_clean_minute(self) -> Tuple[bool, Optional[str]]:
        """
        Called once per validated clean 1-minute bar.
        If SAFE MODE is active, increments clean streak and lifts SAFE MODE after threshold.
        Returns: (resumed, message)
        """
        if not self.status.safe_mode:
            return False, None

        self.status.clean_streak_minutes += 1
        if self.status.clean_streak_minutes >= self.policy.required_clean_minutes_to_resume:
            self.status.safe_mode = False
            msg = f"SAFE MODE lifted after {self.status.clean_streak_minutes} clean minutes."
            return True, msg

        return False, None

    def is_safe_mode(self) -> bool:
        return self.status.safe_mode

    def snapshot(self) -> dict:
        return {
            "safe_mode": self.status.safe_mode,
            "clean_streak_minutes": self.status.clean_streak_minutes,
            "last_issue": None if self.status.last_issue is None else {
                "code": self.status.last_issue.code,
                "message": self.status.last_issue.message
            }
        }
