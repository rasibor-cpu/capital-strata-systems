"""
tools/replay/_telemetry.py

Replay Telemetry Helper
-----------------------
Purpose:
- Provide a reusable progress/ETA printer for long-running replay loops.
- Standardize replay runtime summaries across tools.

Design goals:
- Zero external dependencies
- Safe for large loops (low overhead)
- Works with unknown total counts (ETA optional)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


def _fmt_seconds(seconds: float) -> str:
    if seconds < 0:
        return "?"
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}h {m:02d}m {sec:02d}s"
    if m > 0:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"


@dataclass
class ReplayTelemetry:
    """
    Progress/ETA printer for replay loops.

    Usage:
        t = ReplayTelemetry(
            label="PORTFOLIO REPLAY V5",
            total=total_timestamps,
            print_every=5000,
        )
        for i, ts in enumerate(timestamps, start=1):
            ...
            t.tick(i)

        t.done(processed=total_timestamps)

    Notes:
    - `total` is optional; if absent, ETA will not be printed.
    - Uses wall-clock time for throughput/ETA.
    """
    label: str = "REPLAY"
    total: Optional[int] = None
    print_every: int = 5000
    warmup: int = 2000  # avoid noisy ETA at the very start
    unit: str = "ts"

    _t0: float = 0.0
    _last_print_t: float = 0.0
    _last_i: int = 0

    def __post_init__(self) -> None:
        now = time.time()
        self._t0 = now
        self._last_print_t = now
        self._last_i = 0

        if self.total is not None and self.total <= 0:
            self.total = None

        total_str = f"{self.total:,}" if self.total else "?"
        print(f"[{self.label}] Start | total={total_str} {self.unit}")

    def tick(self, i: int) -> None:
        """
        Call periodically from the replay loop with current counter i (1-based recommended).
        """
        if i <= 0:
            return

        # Print by iteration cadence rather than time to stay deterministic
        if (i % self.print_every) != 0:
            return

        now = time.time()
        elapsed = now - self._t0
        since_last = now - self._last_print_t
        delta_i = i - self._last_i if i > self._last_i else 0

        # Throughput (overall + recent window)
        overall_rate = (i / elapsed) if elapsed > 0 else 0.0
        window_rate = (delta_i / since_last) if since_last > 0 and delta_i > 0 else 0.0

        # ETA only if total known and we're past warmup
        eta_s = -1.0
        pct = None
        if self.total is not None and i >= self.warmup:
            remaining = max(self.total - i, 0)
            eta_s = (remaining / overall_rate) if overall_rate > 0 else -1.0
            pct = min((i / self.total) * 100.0, 100.0)

        if self.total is not None:
            if pct is None:
                print(
                    f"[{self.label}] {i:,}/{self.total:,} {self.unit} | "
                    f"elapsed={_fmt_seconds(elapsed)} | "
                    f"rate={overall_rate:,.1f}/{self.unit}/s (win {window_rate:,.1f})"
                )
            else:
                print(
                    f"[{self.label}] {i:,}/{self.total:,} {self.unit} ({pct:5.1f}%) | "
                    f"elapsed={_fmt_seconds(elapsed)} | "
                    f"rate={overall_rate:,.1f}/{self.unit}/s (win {window_rate:,.1f}) | "
                    f"ETA={_fmt_seconds(eta_s)}"
                )
        else:
            print(
                f"[{self.label}] {i:,} {self.unit} | "
                f"elapsed={_fmt_seconds(elapsed)} | "
                f"rate={overall_rate:,.1f}/{self.unit}/s (win {window_rate:,.1f})"
            )

        self._last_print_t = now
        self._last_i = i

    def done(self, processed: Optional[int] = None) -> None:
        """
        Call once at the end to print a final runtime summary.
        """
        now = time.time()
        elapsed = now - self._t0
        n = processed if processed is not None else self._last_i
        rate = (n / elapsed) if elapsed > 0 and n is not None else 0.0

        total_str = f"{self.total:,}" if self.total else "?"
        n_str = f"{n:,}" if n is not None else "?"
        print(
            f"[{self.label}] Done | processed={n_str}/{total_str} {self.unit} | "
            f"elapsed={_fmt_seconds(elapsed)} | avg_rate={rate:,.1f}/{self.unit}/s"
        )