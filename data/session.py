from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SessionPolicy:
    """
    REA Capital – Trading Engine (Module 1)
    US session policy:
    - Allowed trading window: 09:45–14:30 ET
    - Hard no-trade windows: 09:30–09:45 ET and 15:00–16:00 ET
    All checks are done in America/New_York, input timestamps must be UTC tz-aware.
    """
    tz: str = "America/New_York"

    # Allowed window
    allow_start: time = time(9, 45)
    allow_end: time = time(14, 30)

    # Hard no-trade windows
    no_trade_open_start: time = time(9, 30)
    no_trade_open_end: time = time(9, 45)
    no_trade_close_start: time = time(15, 0)
    no_trade_close_end: time = time(16, 0)

    def is_within_allowed_window(self, ts_utc: datetime) -> bool:
        if ts_utc.tzinfo is None:
            raise ValueError("ts_utc must be timezone-aware UTC")

        tz = ZoneInfo(self.tz)
        ts_local = ts_utc.astimezone(tz)
        t = ts_local.time()

        # Hard no-trade windows
        if self.no_trade_open_start <= t < self.no_trade_open_end:
            return False
        if self.no_trade_close_start <= t < self.no_trade_close_end:
            return False

        # Allowed window
        return self.allow_start <= t < self.allow_end

    def minutes_to_next_allowed(self, ts_utc: datetime) -> int:
        """
        Minutes until next allowed window begins (0 if already allowed).
        """
        if self.is_within_allowed_window(ts_utc):
            return 0

        tz = ZoneInfo(self.tz)
        ts_local = ts_utc.astimezone(tz)

        allow_dt = datetime.combine(ts_local.date(), self.allow_start, tzinfo=tz)
        allow_end_dt = datetime.combine(ts_local.date(), self.allow_end, tzinfo=tz)

        if ts_local >= allow_end_dt:
            allow_dt = allow_dt + timedelta(days=1)

        delta = allow_dt - ts_local
        return max(0, int(delta.total_seconds() // 60))
