from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Bar:
    """
    OHLCV bar.
    Timestamp convention:
    - ts is the OPEN time of the bar
    - ts MUST be timezone-aware UTC
    """
    symbol: str
    timeframe: str  # "1m" or "5m"
    ts: datetime
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0

    def __post_init__(self):
        if self.ts.tzinfo is None:
            raise ValueError("Bar.ts must be timezone-aware (UTC).")


@dataclass(frozen=True)
class DataIssue:
    """
    Represents a data integrity problem that forces SAFE MODE.
    """
    code: str
    message: str
    at: datetime  # UTC timestamp when issue was detected


@dataclass
class FeedStatus:
    """
    Tracks health state of the data feed.
    SAFE MODE is engaged on any inconsistency.
    """
    safe_mode: bool = True
    last_issue: Optional[DataIssue] = None
    clean_streak_minutes: int = 0

