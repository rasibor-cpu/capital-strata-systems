from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from .models import Bar, DataIssue
from .session import SessionPolicy
from .validator_1m import OneMinuteValidator, OneMinuteValidationPolicy
from .health import FeedHealthManager, HealthPolicy
from .builder_5m import FiveMinuteBuilder


@dataclass
class ControllerConfig:
    symbol: str = "SPY"
    # Data health
    required_clean_minutes_to_resume: int = 2
    latency_seconds: int = 60
    max_rel_jump: float = 0.008


class DataController:
    """
    Module 1 Controller:
    - Enforces session window eligibility (time gating)
    - Validates 1m bars
    - Maintains SAFE MODE (auto-resume after 2 clean minutes)
    - Aggregates 1m -> 5m bars

    NOTE:
    - This controller does NOT contain strategy logic.
    - It only answers: "Is data healthy and within allowed window?"
    """

    def __init__(self, cfg: ControllerConfig, session: Optional[SessionPolicy] = None):
        self.cfg = cfg
        self.session = session or SessionPolicy()

        vpol = OneMinuteValidationPolicy(
            latency_seconds=cfg.latency_seconds,
            max_rel_jump=cfg.max_rel_jump,
            require_ohlc_consistency=True
        )
        self.validator = OneMinuteValidator(vpol)
        self.health = FeedHealthManager(HealthPolicy(required_clean_minutes_to_resume=cfg.required_clean_minutes_to_resume))
        self.builder = FiveMinuteBuilder(symbol=cfg.symbol)

    def ingest_1m(self, bar1m: Bar, received_at_utc: Optional[datetime] = None) -> Tuple[bool, Optional[Bar], Optional[DataIssue]]:
        """
        Ingest one 1-minute bar.
        Returns:
          (ok_1m, bar5m_or_none, issue_or_none)

        - ok_1m: whether the 1m bar passed validation
        - bar5m_or_none: a completed 5m bar if one was formed
        - issue_or_none: DataIssue if validation failed
        """
        if received_at_utc is None:
            received_at_utc = datetime.now(timezone.utc)

        ok, issue = self.validator.validate(bar1m, received_at_utc)
        if not ok:
            self.health.mark_issue(issue)
            return False, None, issue

        # mark clean minute; may lift SAFE MODE after threshold
        self.health.mark_clean_minute()

        bar5m = self.builder.push_1m(bar1m)
        return True, bar5m, None

    def is_time_eligible(self, ts_utc: datetime) -> bool:
        """
        True if within allowed US session window (policy rules).
        """
        return self.session.is_within_allowed_window(ts_utc)

    def is_data_eligible(self) -> bool:
        """
        True if SAFE MODE is not active.
        """
        return not self.health.is_safe_mode()

    def eligibility_snapshot(self, ts_utc: datetime) -> dict:
        """
        Combined eligibility view: time + data.
        This is the only thing the strategy layer should rely on at this stage.
        """
        return {
            "time_ok": self.is_time_eligible(ts_utc),
            "data_ok": self.is_data_eligible(),
            "health": self.health.snapshot(),
            "minutes_to_next_allowed": self.session.minutes_to_next_allowed(ts_utc),
        }
