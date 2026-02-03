from __future__ import annotations

"""
REA Capital – Trading Engine (FX Replay Runner)
v4 — FX pairs replay + carry (swap) + Bollinger Bands (optional indicator layer)

CRITICAL DESIGN GOAL
--------------------
This runner must remain adapter-agnostic:
- Any source that outputs rows with (timestamp, pair, mid) can be wired into the same pipeline.
- No hard-coded pair filters.
- No assumptions about only one pair.
- Timeframes are configurable (NOT limited to 1m/5m).

This file reads CSV only. Other live adapters (TwelveData, etc.) remain untouched.

Python: 3.14 compatible
"""

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Iterable, Any, Tuple

# Optional indicator layer (you added this in indicators/bollinger.py)
# If missing, the runner still works (Bollinger becomes "disabled").
try:
    from indicators.bollinger import compute_bollinger  # type: ignore
    _BOLLINGER_OK = True
except Exception:
    compute_bollinger = None  # type: ignore
    _BOLLINGER_OK = False


# =========================
# Helpers
# =========================

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(",", "")
        if not s:
            return default
        return float(s)
    except Exception:
        return default


def _parse_ts_to_dt(x: str) -> datetime:
    """
    Accepts:
      - ISO8601 like 2026-01-22T14:00:00Z
      - ISO8601 with offset
      - epoch seconds (int/float as string)
    Returns: timezone-aware UTC datetime.
    """
    s = (x or "").strip()
    if not s:
        return datetime.now(timezone.utc)

    # epoch?
    try:
        if s.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
    except Exception:
        pass

    # ISO8601
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _pair_norm(pair: str) -> str:
    # Keep adapter-agnostic normalization: accept EUR/USD or EURUSD.
    p = (pair or "").strip().upper()
    return p.replace("/", "")


def _pair_split(pair: str) -> Tuple[str, str]:
    p = _pair_norm(pair)
    if len(p) >= 6:
        return p[:3], p[3:6]
    return p, ""


# =========================
# Carry / forward (simple)
# =========================

@dataclass(frozen=True)
class FXRateTable:
    rates: Dict[str, float]

    def r(self, ccy: str, default: float = 0.0) -> float:
        return float(self.rates.get((ccy or "").strip().upper(), default))


@dataclass(frozen=True)
class FXDerivativesConfig:
    day_count: str = "ACT/365"
    swap_point_scale: float = 10000.0


@dataclass(frozen=True)
class CarryResult:
    pair: str
    base: str
    quote: str
    tenor_days: int
    carry_annual: float
    carry_period: float
    swap_points: float
    forward_est: float


def _dt_years(days: int, day_count: str) -> float:
    dc = (day_count or "").upper().strip()
    denom = 365.0 if dc == "ACT/365" else 360.0
    return float(days) / denom


def compute_carry_and_forward(pair: str, spot: float, rates: FXRateTable, cfg: FXDerivativesConfig, tenor_days: int = 1) -> CarryResult:
    base, quote = _pair_split(pair)
    r_b = rates.r(base, 0.0)
    r_q = rates.r(quote, 0.0)
    dt = _dt_years(max(1, int(tenor_days)), cfg.day_count)

    carry_annual = (r_b - r_q)
    carry_period = carry_annual * dt

    denom = max(0.01, (1.0 + r_q * dt))
    numer = (1.0 + r_b * dt)
    forward = spot * (numer / denom)
    swap_points = (forward - spot) * cfg.swap_point_scale

    return CarryResult(pair=_pair_norm(pair), base=base, quote=quote, tenor_days=tenor_days,
                       carry_annual=carry_annual, carry_period=carry_period,
                       swap_points=swap_points, forward_est=forward)


# =========================
# Replay structures
# =========================

@dataclass(frozen=True)
class Tick:
    ts: datetime
    pair: str
    mid: float


@dataclass(frozen=True)
class Bar:
    ts_open: datetime
    ts_close: datetime
    pair: str
    close: float
    vwap: float
    n: int


class BarBuilder:
    """
    Generic time-bucket bar builder.

    IMPORTANT:
    - Finalizes a bar whenever the incoming tick moves into a new bucket.
    - This fixes the "bars_1m=0/bars_5m=0" symptom when ticks are well-formed but buckets never close.
    """
    def __init__(self, tf_sec: int) -> None:
        self.tf_sec = int(tf_sec)
        self._buf: Dict[str, List[Tick]] = {}

    def push(self, t: Tick) -> Optional[Bar]:
        pair = t.pair
        buf = self._buf.get(pair)

        bucket = int(t.ts.timestamp()) // self.tf_sec

        if buf is None or len(buf) == 0:
            self._buf[pair] = [t]
            return None

        cur_bucket = int(buf[0].ts.timestamp()) // self.tf_sec

        # same bucket -> accumulate
        if bucket == cur_bucket:
            buf.append(t)
            return None

        # new bucket -> finalize previous bar, then start new bucket
        bar = self._to_bar(pair, buf)
        self._buf[pair] = [t]
        return bar

    def _to_bar(self, pair: str, ticks: List[Tick]) -> Bar:
        ticks = sorted(ticks, key=lambda x: x.ts)
        mids = [x.mid for x in ticks]
        vwap = sum(mids) / max(1, len(mids))
        return Bar(
            ts_open=ticks[0].ts,
            ts_close=ticks[-1].ts,
            pair=pair,
            close=mids[-1],
            vwap=vwap,
            n=len(mids),
        )


# =========================
# Prompt
# =========================

class PromptGen:
    def build(self, bar: Bar, carry: CarryResult, bb_summary: Optional[Dict[str, float]]) -> str:
        lines: List[str] = []
        lines.append("REA FX Prompt (SANITY PROBE — NO EXECUTION)")
        lines.append(f"ts_utc: {_fmt_dt(bar.ts_close)}")
        lines.append(f"pair: {bar.pair}")
        lines.append(f"close={bar.close:.6f} vwap={bar.vwap:.6f}")
        lines.append(f"carry_annual={carry.carry_annual:+.4f}")
        lines.append(f"swap_points≈{carry.swap_points:+.2f}")

        if bb_summary is not None:
            lines.append("bollinger:")
            lines.append(f"  mid={bb_summary['mid']:.6f}")
            lines.append(f"  upper={bb_summary['upper']:.6f}")
            lines.append(f"  lower={bb_summary['lower']:.6f}")

        lines.append("-" * 72)
        return "\n".join(lines)


# =========================
# Runner
# =========================

def load_ticks(csv_path: str) -> Iterable[Tick]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ts_raw = row.get("timestamp", "") or row.get("ts", "") or row.get("time", "")
            pair_raw = row.get("pair", "") or row.get("symbol", "")
            mid_raw = row.get("mid", "") or row.get("price", "") or row.get("close", "")

            ts = _parse_ts_to_dt(str(ts_raw))
            pair = _pair_norm(str(pair_raw))
            mid = _safe_float(mid_raw, 0.0)

            if not pair or mid <= 0.0:
                continue

            yield Tick(ts=ts, pair=pair, mid=mid)


def run() -> Dict[str, int]:
    # CSV source: allow env override
    csv_path = os.environ.get("REA_FX_CSV", "data/fx_pairs.csv")

    # Output file (prompts)
    out_path = os.environ.get("REA_FX_OUT", "out/fx_prompts.txt")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Timeframes (NOT limited to 1m/5m)
    tf_fast = int(os.environ.get("REA_TF_FAST_SEC", "60"))      # default 60s
    tf_slow = int(os.environ.get("REA_TF_SLOW_SEC", "300"))     # default 300s

    min_slow_bars = int(os.environ.get("REA_MIN_SLOW_BARS", "40"))  # regime allow threshold

    # Carry model inputs
    rates = FXRateTable(rates={
        "USD": 0.05,
        "EUR": 0.035,
        "GBP": 0.045,
        "JPY": 0.005,
        "CHF": 0.01,
        "CAD": 0.04,
        "AUD": 0.042,
        "NZD": 0.043,
    })
    derivs = FXDerivativesConfig()

    # Bollinger optional
    BB_PERIOD = int(os.environ.get("REA_BB_PERIOD", "20"))
    BB_K = float(os.environ.get("REA_BB_K", "2.0"))

    bb_fast = BarBuilder(tf_fast)
    bb_slow = BarBuilder(tf_slow)
    pg = PromptGen()

    bars_fast = 0
    bars_slow = 0
    regime_allow = 0
    regime_block = 0
    prompts = 0

    # per-pair slow-bar counts + buffers for BB
    slow_counts: Dict[str, int] = {}
    price_buf: Dict[str, List[float]] = {}

    with open(out_path, "w", encoding="utf-8") as out:
        for t in load_ticks(csv_path):
            b_fast = bb_fast.push(t)
            if b_fast is None:
                continue
            bars_fast += 1

            # feed slow builder with fast-bar closes
            b_slow = bb_slow.push(Tick(ts=b_fast.ts_close, pair=b_fast.pair, mid=b_fast.close))
            if b_slow is None:
                continue
            bars_slow += 1

            cnt = slow_counts.get(b_slow.pair, 0) + 1
            slow_counts[b_slow.pair] = cnt

            if cnt < min_slow_bars:
                regime_block += 1
                continue

            regime_allow += 1

            carry = compute_carry_and_forward(b_slow.pair, b_slow.close, rates, derivs, tenor_days=1)

            # Bollinger (optional, safe)
            bb_summary: Optional[Dict[str, float]] = None
            buf = price_buf.setdefault(b_slow.pair, [])
            buf.append(b_slow.close)
            if len(buf) > max(2000, BB_PERIOD * 50):
                # bounded memory
                buf[:] = buf[-max(2000, BB_PERIOD * 50):]

            if _BOLLINGER_OK and compute_bollinger is not None and len(buf) >= BB_PERIOD:
                bb = compute_bollinger(buf, BB_PERIOD, BB_K)
                # keep output minimal and stable
                bb_summary = {"mid": float(bb.mid), "upper": float(bb.upper), "lower": float(bb.lower)}

            out.write(pg.build(b_slow, carry, bb_summary) + "\n")
            prompts += 1

    print("\nREA FX Runner Summary")
    print("-" * 72)
    print(f"csv_path: {csv_path}")
    print(f"out_path: {out_path}")
    print(f"tf_fast_sec: {tf_fast}")
    print(f"tf_slow_sec: {tf_slow}")
    print(f"bars_fast: {bars_fast}")
    print(f"bars_slow: {bars_slow}")
    print(f"regime_allow: {regime_allow}")
    print(f"regime_block: {regime_block}")
    print(f"prompts_generated: {prompts}")
    print("-" * 72)

    return {
        "bars_fast": bars_fast,
        "bars_slow": bars_slow,
        "regime_allow": regime_allow,
        "regime_block": regime_block,
        "prompts_generated": prompts,
    }


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
