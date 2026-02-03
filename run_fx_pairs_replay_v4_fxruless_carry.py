from __future__ import annotations

"""
REA Capital – Trading Engine (FX Replay Runner)
v4 (carry + swaps awareness) + Bollinger Bands (optional)
PROMPT-ONLY / ANALYSIS-ONLY: no execution, no orders.

ROOT FIX (2026-02-02):
- BarBuilder.push() MUST return a completed Bar when a time bucket closes.
- This unblocks: bars_1m/bars_5m counts, buffers, indicators, and prompt output.

Compatibility:
- Does NOT touch any adapter or live feed modules.
- Reads CSV from REA_FX_CSV env var (or default).
- Writes prompts to out/fx_prompts.txt

Python: 3.14 compatible
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Iterable, Any
import csv
import os
import math
import hashlib


# =========================
# Helpers
# =========================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _parse_iso8601(s: str) -> datetime:
    s = (s or "").strip()
    if not s:
        return _utc_now()
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        # fallback: try epoch seconds
        try:
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
        except Exception:
            return _utc_now()

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(",", "")
        if s == "":
            return default
        return float(s)
    except Exception:
        return default

def _fmt_dt(dt: datetime) -> str:
    try:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    except Exception:
        return str(dt)

def _pair_norm(pair: str) -> str:
    return (pair or "").strip().upper().replace("/", "")

def _pair_split(pair: str) -> Tuple[str, str]:
    p = _pair_norm(pair)
    if len(p) >= 6:
        return p[:3], p[3:6]
    return p, ""


# =========================
# Carry / Swap (simple)
# =========================

@dataclass(frozen=True)
class FXRateTable:
    rates: Dict[str, float] = field(default_factory=dict)

    def r(self, ccy: str, default: float = 0.0) -> float:
        return float(self.rates.get((ccy or "").upper().strip(), default))

@dataclass(frozen=True)
class FXDerivativesConfig:
    day_count: str = "ACT/365"
    swap_point_scale: float = 10000.0

def _dt_years(days: int, day_count: str) -> float:
    denom = 365.0 if (day_count or "").upper() == "ACT/365" else 360.0
    return float(days) / denom

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

def compute_carry_and_forward(
    pair: str,
    spot: float,
    rates: FXRateTable,
    cfg: FXDerivativesConfig,
    tenor_days: int = 1
) -> CarryResult:
    base, quote = _pair_split(pair)
    r_b = rates.r(base, 0.0)
    r_q = rates.r(quote, 0.0)
    dt = _dt_years(max(1, int(tenor_days)), cfg.day_count)

    carry_annual = (r_b - r_q)
    carry_period = carry_annual * dt

    denom = max(0.01, (1.0 + r_q * dt))
    numer = (1.0 + r_b * dt)
    forward = float(spot) * (numer / denom)
    swap_points = (forward - float(spot)) * cfg.swap_point_scale

    return CarryResult(pair=_pair_norm(pair), base=base, quote=quote, tenor_days=tenor_days,
                      carry_annual=carry_annual, carry_period=carry_period,
                      swap_points=swap_points, forward_est=forward)


# =========================
# Bollinger Bands (optional)
# =========================

@dataclass(frozen=True)
class BollingerState:
    mid: float
    upper: float
    lower: float
    ma: float
    std: float
    period: int

def compute_bollinger(values: List[float], period: int = 20, k: float = 2.0) -> Optional[BollingerState]:
    if period <= 1:
        return None
    if len(values) < period:
        return None
    window = values[-period:]
    ma = sum(window) / float(period)
    var = sum((x - ma) ** 2 for x in window) / float(period)
    std = math.sqrt(var)
    mid = values[-1]
    upper = ma + k * std
    lower = ma - k * std
    return BollingerState(mid=mid, upper=upper, lower=lower, ma=ma, std=std, period=period)


# =========================
# Replay structures
# =========================

@dataclass
class Tick:
    ts: datetime
    pair: str
    bid: float
    ask: float
    mid: float

@dataclass
class Bar:
    ts_open: datetime
    ts_close: datetime
    pair: str
    o: float
    h: float
    l: float
    c: float
    vwap: float
    n: int


class BarBuilder:
    """
    Generic bar builder from ticks.
    FIXED: push() returns a completed Bar when the bucket changes.
    """
    def __init__(self, tf_sec: int) -> None:
        self.tf = int(tf_sec)
        self._buf: Dict[str, List[Tick]] = {}

    def push(self, t: Tick) -> Optional[Bar]:
        key = t.pair
        bucket = int(t.ts.timestamp()) // self.tf

        buf = self._buf.get(key)
        if buf is None:
            self._buf[key] = [t]
            return None

        cur_bucket = int(buf[0].ts.timestamp()) // self.tf
        if bucket == cur_bucket:
            buf.append(t)
            return None

        # bucket changed => close previous bar and start new bucket
        bar = self._to_bar(buf, key)
        self._buf[key] = [t]
        return bar

    def _to_bar(self, ticks: List[Tick], pair: str) -> Bar:
        ticks = sorted(ticks, key=lambda x: x.ts)
        o = ticks[0].mid
        c = ticks[-1].mid
        h = max(x.mid for x in ticks)
        l = min(x.mid for x in ticks)
        vwap = sum(x.mid for x in ticks) / float(len(ticks))
        return Bar(
            ts_open=ticks[0].ts,
            ts_close=ticks[-1].ts,
            pair=pair,
            o=o, h=h, l=l, c=c,
            vwap=vwap,
            n=len(ticks),
        )


# =========================
# Governance (locked policy in prompt)
# =========================

@dataclass(frozen=True)
class ProfitTakingPolicy:
    profit_tiers: List[float] = field(default_factory=lambda: [0.10, 0.20, 0.35, 0.50])
    max_reentry_fraction_of_realized_profit: float = 0.50
    principal_protection: bool = True
    lifecycle_reset_on_reentry: bool = True
    martingale_allowed: bool = False
    use_unrealized_gains_for_reentry: bool = False

    def policy_hash(self) -> str:
        s = f"{self.profit_tiers}|{self.max_reentry_fraction_of_realized_profit}|{self.principal_protection}|{self.lifecycle_reset_on_reentry}|{self.martingale_allowed}|{self.use_unrealized_gains_for_reentry}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:64]


# =========================
# Runner config
# =========================

@dataclass
class RunnerConfig:
    csv_path: str = "data/fx_pairs.csv"
    timestamp_col: str = "timestamp"
    pair_col: str = "pair"
    bid_col: str = "bid"
    ask_col: str = "ask"
    mid_col: str = "mid"

    build_5m: bool = True
    min_5m_bars_for_allow: int = 40

    # Indicator controls (optional)
    enable_bollinger: bool = True
    bb_period: int = 20
    bb_k: float = 2.0

    # Sanity probe epsilon: minimal VWAP distance gate for prompt generation
    diag_epsilon: float = 0.0001

    prompt_only: bool = True  # always True here

    rate_table: FXRateTable = field(default_factory=lambda: FXRateTable({
        "USD": 0.05,
        "EUR": 0.035,
        "GBP": 0.045,
        "JPY": 0.005,
        "CHF": 0.01,
        "CAD": 0.04,
        "AUD": 0.042,
        "NZD": 0.043,
    }))
    derivs: FXDerivativesConfig = field(default_factory=FXDerivativesConfig)
    governance_policy: ProfitTakingPolicy = field(default_factory=ProfitTakingPolicy)

    prompts_out: str = "out/fx_prompts.txt"


# =========================
# Prompt generator
# =========================

def _fmt_pct_list(xs: List[float]) -> str:
    return ", ".join(f"{int(round(x*100))}%" for x in xs)

def build_prompt(
    bar: Bar,
    carry: CarryResult,
    policy: ProfitTakingPolicy,
    bb: Optional[BollingerState],
) -> str:
    lines: List[str] = []
    lines.append("REA FX Prompt (SANITY PROBE - NO EXECUTION)")
    lines.append(f"ts_utc: {_fmt_dt(bar.ts_close)}")
    lines.append(f"pair: {bar.pair}")
    lines.append(f"c={bar.c:.6f} vwap={bar.vwap:.6f}")
    lines.append(f"carry_annual={carry.carry_annual:+.4f}")
    lines.append(f"swap_points~{carry.swap_points:+.2f}")

    if bb is not None:
        lines.append("")
        lines.append("INDICATORS:")
        lines.append(f"bollinger_period={bb.period} k={2.0:.1f}")
        lines.append(f"bb_ma={bb.ma:.6f} bb_std={bb.std:.6f}")
        lines.append(f"bb_upper={bb.upper:.6f} bb_lower={bb.lower:.6f}")

    lines.append("")
    lines.append("GOVERNANCE (LOCKED):")
    lines.append(f"profit_tiers: {_fmt_pct_list(policy.profit_tiers)}")
    lines.append(f"max_reentry_fraction_of_realized_profit: {int(round(policy.max_reentry_fraction_of_realized_profit*100))}%")
    lines.append(f"martingale_allowed: {policy.martingale_allowed}")
    lines.append(f"use_unrealized_gains_for_reentry: {policy.use_unrealized_gains_for_reentry}")
    lines.append(f"policy_hash: {policy.policy_hash()}")

    return "\n".join(lines)


# =========================
# IO
# =========================

def load_ticks(cfg: RunnerConfig) -> Iterable[Tick]:
    if not os.path.exists(cfg.csv_path):
        raise FileNotFoundError(f"CSV not found: {cfg.csv_path}")

    with open(cfg.csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ts = _parse_iso8601(row.get(cfg.timestamp_col, ""))
            pair = _pair_norm(row.get(cfg.pair_col, ""))
            bid = _safe_float(row.get(cfg.bid_col))
            ask = _safe_float(row.get(cfg.ask_col))
            mid = _safe_float(row.get(cfg.mid_col))
            if mid == 0.0:
                if bid and ask:
                    mid = (bid + ask) / 2.0
                elif bid:
                    mid = bid
                elif ask:
                    mid = ask

            if not pair or mid == 0.0:
                continue

            if bid == 0.0:
                bid = mid
            if ask == 0.0:
                ask = mid

            yield Tick(ts=ts, pair=pair, bid=bid, ask=ask, mid=mid)


# =========================
# Core run
# =========================

def run(cfg: RunnerConfig) -> Dict[str, Any]:
    bb1 = BarBuilder(60)
    bb5 = BarBuilder(300)

    bars_1m = 0
    bars_5m = 0
    regime_allow = 0
    regime_block = 0
    prompts_generated = 0

    # per pair 5m bar count (regime gate)
    pair_5m_count: Dict[str, int] = {}
    # per pair close buffer (for Bollinger)
    closes: Dict[str, List[float]] = {}

    os.makedirs(os.path.dirname(cfg.prompts_out), exist_ok=True)
    with open(cfg.prompts_out, "w", encoding="utf-8") as out:
        for t in load_ticks(cfg):
            b1 = bb1.push(t)
            if b1 is None:
                continue
            bars_1m += 1

            # build 5m bars using the 1m close as the tick input
            b5 = bb5.push(Tick(ts=b1.ts_close, pair=b1.pair, bid=b1.c, ask=b1.c, mid=b1.c))
            if b5 is None:
                continue
            bars_5m += 1

            # regime gate by minimum 5m bars per pair
            cnt = pair_5m_count.get(b5.pair, 0) + 1
            pair_5m_count[b5.pair] = cnt

            if cnt < int(cfg.min_5m_bars_for_allow):
                regime_block += 1
                continue
            regime_allow += 1

            # carry estimate
            carry = compute_carry_and_forward(b5.pair, b5.c, cfg.rate_table, cfg.derivs, tenor_days=1)

            # sanity epsilon gate (VWAP distance)
            if abs(b5.c - b5.vwap) < float(cfg.diag_epsilon):
                continue

            # indicator update
            bb_state: Optional[BollingerState] = None
            if cfg.enable_bollinger:
                buf = closes.setdefault(b5.pair, [])
                buf.append(float(b5.c))
                bb_state = compute_bollinger(buf, period=int(cfg.bb_period), k=float(cfg.bb_k))

            prompt = build_prompt(b5, carry, cfg.governance_policy, bb_state)
            out.write(prompt + "\n" + ("-" * 72) + "\n")
            prompts_generated += 1

    return {
        "bars_1m": bars_1m,
        "bars_5m": bars_5m,
        "regime_allow": regime_allow,
        "regime_block": regime_block,
        "prompts_generated": prompts_generated,
        "csv_path": cfg.csv_path,
        "prompts_out": cfg.prompts_out,
    }


def main() -> int:
    csv_path = os.environ.get("REA_FX_CSV", "data/fx_pairs.csv")
    cfg = RunnerConfig(csv_path=csv_path)
    stats = run(cfg)

    print("\nREA FX Runner Summary")
    print("-" * 72)
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("-" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
