from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from .models import Bar, DataIssue


@dataclass
class OneMinuteValidationPolicy:
    """
    Validation policy for 1-minute bars.
    """
    latency_seconds: int = 60
    max_rel_jump: float = 0.008
    require_ohlc_consistency: bool = True


class OneMinuteValidator:
    def __init__(self, policy: OneMinuteValidationPolicy):
        self.policy = policy
        self._prev_bar: Optional[Bar] = None

    @staticmethod
    def _is_utc(dt: datetime) -> bool:
        return dt.tzinfo is not None and dt.utcoffset() == timedelta(0)

    def validate(
        self,
        bar: Bar,
        received_at_utc: datetime
    ) -> Tuple[bool, Optional[DataIssue]]:
        now_utc = datetime.now(timezone.utc)

        if bar.timeframe != "1m":
            return False, DataIssue("TF_MISMATCH", "Expected 1m bar", now_utc)

        if bar.ts.tzinfo is None or not self._is_utc(bar.ts):
            return False, DataIssue("TS_NOT_UTC", "Bar timestamp must be UTC", now_utc)

        if received_at_utc.tzinfo is None or not self._is_utc(received_at_utc):
            return False, DataIssue("RX_NOT_UTC", "received_at_utc must be UTC", now_utc)

        bar_close = bar.ts + timedelta(minutes=1)
        latest_ok = bar_close + timedelta(seconds=self.policy.latency_seconds)
        if received_at_utc > latest_ok:
            return False, DataIssue("LATE_BAR", "Bar arrived late", received_at_utc)

        if self.policy.require_ohlc_consistency:
            if bar.h < bar.l:
                return False, DataIssue("OHLC_RANGE", "High < Low", received_at_utc)
            if not (bar.l <= bar.o <= bar.h and bar.l <= bar.c <= bar.h):
                return False, DataIssue("OHLC_BAD", "Invalid OHLC values", received_at_utc)

        if self._prev_bar:
            if bar.ts <= self._prev_bar.ts:
                return False, DataIssue("OUT_OF_ORDER", "Bar out of order", received_at_utc)

            expected = self._prev_bar.ts + timedelta(minutes=1)
            if bar.ts != expected:
                return False, DataIssue("GAP", "Missing 1-minute bar", received_at_utc)

            prev_close = self._prev_bar.c
            if prev_close > 0:
                rel_jump = abs((bar.c - prev_close) / prev_close)
                if rel_jump > self.policy.max_rel_jump:
                    return False, DataIssue("ABNORMAL_JUMP", "Excessive price jump", received_at_utc)

        self._prev_bar = bar
        return True, None
