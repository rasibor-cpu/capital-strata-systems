from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from .models import Bar, DataIssue


@dataclass
class OneMinuteValidationPolicy:
    """
    Validation policy for 1-minute bars (Module 1).
    """
    # Bar must arrive within this many seconds after its close timestamp.
    latency_seconds: int = 60

    # Flag abnormal 1-minute close-to-close jumps (relative).
    # For SPY, 0.8% per minute is a conservative sanity threshold for bad ticks.
    max_rel_jump: float = 0.008

    require_ohlc_consistency: bool = True


class OneMinuteValidator:
    def __init__(self, policy: OneMinuteValidationPolicy):
        self.policy = policy
        self._prev_bar: Optional[Bar] = None

    @staticmethod
    def _is_utc(dt: datetime) -> bool:
        return dt.tzinfo is not None and dt.utcoffset() == timedelta(0)

    def validate(self, bar: Bar, received_at_utc: datetime) -> Tuple[bool, Optional[DataIssue]]:
        """
        Validate a single 1-minute bar in sequence.
        Returns: (ok, issue)
        """
        now_utc = datetime.now(timezone.utc)

        if bar.timeframe != "1m":
            return False, DataIssue("TF_MISMATCH", "Expected 1m bar", now_utc)

        if bar.ts.tzinfo is None or not self._is_utc(bar.ts):
            return False, DataIssue("TS_NOT_UTC", "Bar timestamp must be timezone-aware UTC", now_utc)

        if received_at_utc.tzinfo is None or not self._is_utc(received_at_utc):
            return False, DataIssue("RX_NOT_UTC", "received_at_utc must be timezone-aware UTC", now_utc)

        # Latency check
        bar_close = bar.ts + timedelta(minutes=1)
        latest_ok = bar_close + timedelta(seconds=self.policy.latency_seconds)
        if received_at_utc > latest_ok:
            return False, DataIssue("LATE_BAR", f"Bar arrived late (> {self.policy.latency_seconds}s)", received_at_utc)

        # OHLC sanity
        if self.policy.require_ohlc_consistency:
            if bar.h < bar.l:
                return False, DataIssue("OHLC_RANGE", "High < Low", received_at_utc)
            if not (bar.l <= bar.o <= bar.h and bar.l <= bar.c <= bar.h):
                return False, DataIssue("OHLC_BAD", "OHLC values inconsistent", received_at_utc)

        # Sequence checks
        if self._prev_bar is not None:
            if bar.ts <= self._prev_bar.ts:
                return False, DataIssue("OUT_OF_ORDER", "Bar timestamp out of order", received_at_utc)

            expected_next = self._prev_bar.ts + timedelta(minutes=1)
            if bar.ts != expected_next:
                return False, DataIssue("GAP", f"Missing 1m bar(s). Expected {expected_next.isoformat()}", received_at_utc)

            # Abnormal jump check (close-to-close)
            prev_c = self._prev_bar.c
            if prev_c > 0:
                rel = abs((bar.c - prev_c) / prev_c)
                if rel > self.policy.max_rel_jump:
                    return False, DataIssue(
                        "ABNORMAL_JUMP",
                        f"Close jump {rel:.3%} exceeds threshold {self.policy.max_rel_jump:.3%}",
                        received_at_utc
                    )

        # All good
        self._prev_bar = bar
        return True, None
