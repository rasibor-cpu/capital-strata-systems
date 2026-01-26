from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import List, Optional

from .models import Bar


@dataclass
class FiveMinuteBuilder:
    """
    Builds 5-minute bars from validated 1-minute bars.

    Assumptions:
    - 1-minute bars are already validated (gap-free, ordered).
    - bar.ts is the OPEN time in UTC.
    """
    symbol: str
    _buffer: List[Bar] = None

    def __post_init__(self):
        if self._buffer is None:
            self._buffer = []

    @staticmethod
    def _floor_to_5m(ts: datetime) -> datetime:
        m = (ts.minute // 5) * 5
        return ts.replace(minute=m, second=0, microsecond=0)

    def push_1m(self, bar1m: Bar) -> Optional[Bar]:
        if bar1m.symbol != self.symbol or bar1m.timeframe != "1m":
            return None

        self._buffer.append(bar1m)

        # Wait until we have at least 5 bars
        if len(self._buffer) < 5:
            return None

        # Align buffer to 5-minute boundary
        start = self._floor_to_5m(self._buffer[0].ts)
        if self._buffer[0].ts != start:
            # drop oldest until aligned
            self._buffer.pop(0)
            return None

        # Ensure contiguous minutes
        for i in range(5):
            if self._buffer[i].ts != start + timedelta(minutes=i):
                # reset conservatively to avoid creating wrong 5m bars
                self._buffer = []
                return None

        o = self._buffer[0].o
        h = max(b.h for b in self._buffer)
        l = min(b.l for b in self._buffer)
        c = self._buffer[-1].c
        v = sum(b.v for b in self._buffer)

        bar5m = Bar(
            symbol=self.symbol,
            timeframe="5m",
            ts=start,
            o=o, h=h, l=l, c=c, v=v
        )

        self._buffer.clear()
        return bar5m
