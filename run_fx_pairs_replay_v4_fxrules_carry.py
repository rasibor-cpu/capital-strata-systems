from __future__ import annotations

"""
REA Capital – Trading Engine (FX Replay Runner)
v4 — FX pairs + swaps/carry rules + FX-derivatives awareness + pluggable news sources

SANITY PROBE (EPSILON TEST) INCLUDED
-----------------------------------
- Adds a minimal VWAP-distance epsilon gate before prompt generation.
- RegimeGate unchanged.
- Prompt-only (NO execution).
- Purpose: verify end-to-end gating wiring.

Python: 3.14 compatible
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Iterable, Any
import csv
import math
import os
import traceback
import urllib.request
import xml.etree.ElementTree as ET


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

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _fmt_dt(dt: datetime) -> str:
    try:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    except Exception:
        return str(dt)

def _pair_split(pair: str) -> Tuple[str, str]:
    p = (pair or "").strip().upper().replace("/", "")
    if len(p) != 6:
        return (p[:3], p[3:]) if len(p) >= 6 else (p, "")
    return p[:3], p[3:]


# =========================
# Config
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


@dataclass
class NewsConfig:
    enabled: bool = True
    lookback_minutes: int = 360
    max_items: int = 25
    rss_urls: List[str] = field(default_factory=lambda: [
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "https://www.ecb.europa.eu/rss/press.html",
        "https://www.bankofengland.co.uk/rss/news",
    ])
    reuters_api_key: Optional[str] = None
    bloomberg_api_key: Optional[str] = None


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
    prompt_only: bool = True

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
    news: NewsConfig = field(default_factory=NewsConfig)

    prompts_out: str = "out/fx_prompts.txt"


# =========================
# News + Risk
# =========================

@dataclass(frozen=True)
class NewsItem:
    ts: datetime
    title: str
    source: str
    url: str = ""

class EventRiskScorer:
    KEYWORDS: Dict[str, float] = {
        "rate": 0.15, "inflation": 0.20, "cpi": 0.20, "jobs": 0.15,
        "payroll": 0.20, "nfp": 0.25, "fomc": 0.30,
        "ecb": 0.20, "boe": 0.20, "boj": 0.20,
        "hawkish": 0.20, "dovish": 0.20,
        "sanction": 0.25, "war": 0.35, "geopolitical": 0.25,
        "oil": 0.15, "crisis": 0.35, "default": 0.35,
        "bank": 0.20, "liquidity": 0.25,
    }

    def score(self, headlines: List[NewsItem]) -> float:
        score = 0.0
        for it in headlines:
            title = (it.title or "").lower()
            local = sum(w for k, w in self.KEYWORDS.items() if k in title)
            score += min(local, 0.50)
        return _clamp(score, 0.0, 1.0)


# =========================
# Carry / Swap
# =========================

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

    return CarryResult(pair, base, quote, tenor_days, carry_annual, carry_period, swap_points, forward)


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
    def __init__(self, tf_sec: int) -> None:
        self.tf = tf_sec
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
        bar = self._to_bar(buf, key)
        self._buf[key] = [t]
        return bar

    def _to_bar(self, ticks: List[Tick], pair: str) -> Bar:
        ticks = sorted(ticks, key=lambda x: x.ts)
        o = ticks[0].mid
        c = ticks[-1].mid
        h = max(x.mid for x in ticks)
        l = min(x.mid for x in ticks)
        vwap = sum(x.mid for x in ticks) / len(ticks)
        return Bar(ticks[0].ts, ticks[-1].ts, pair, o, h, l, c, vwap, len(ticks))


# =========================
# Prompt
# =========================

@dataclass
class Prompt:
    ts: datetime
    pair: str
    text: str

class FXPromptGenerator:
    def build(self, bar: Bar, carry: CarryResult) -> Prompt:
        txt = []
        txt.append("REA FX Prompt (SANITY PROBE — NO EXECUTION)")
        txt.append(f"ts_utc: {_fmt_dt(bar.ts_close)}")
        txt.append(f"pair: {bar.pair}")
        txt.append(f"c={bar.c:.6f} vwap={bar.vwap:.6f}")
        txt.append(f"carry_annual={carry.carry_annual:+.4f}")
        txt.append(f"swap_points≈{carry.swap_points:+.2f}")
        return Prompt(bar.ts_close, bar.pair, "\n".join(txt))


# =========================
# Runner
# =========================

def load_ticks(cfg: RunnerConfig) -> Iterable[Tick]:
    if not os.path.exists(cfg.csv_path):
        raise FileNotFoundError(f"CSV not found: {cfg.csv_path}")

    with open(cfg.csv_path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = _parse_iso8601(row.get(cfg.timestamp_col, ""))
            pair = (row.get(cfg.pair_col, "") or "").strip().upper()
            bid = _safe_float(row.get(cfg.bid_col))
            ask = _safe_float(row.get(cfg.ask_col))
            mid = _safe_float(row.get(cfg.mid_col))
            if mid == 0.0:
                mid = (bid + ask) / 2.0 if bid and ask else 0.0
            if not pair or mid == 0.0:
                continue
            yield Tick(ts, pair, bid or mid, ask or mid, mid)

def run(cfg: RunnerConfig) -> Dict[str, Any]:
    bb1 = BarBuilder(60)
    bb5 = BarBuilder(300)

    prompts: List[Prompt] = []
    pg = FXPromptGenerator()

    bars_1m = bars_5m = regime_allow = regime_block = 0
    pair_5m_count: Dict[str, int] = {}

    for t in load_ticks(cfg):
        b1 = bb1.push(t)
        if not b1:
            continue
        bars_1m += 1

        b5 = bb5.push(Tick(b1.ts_close, b1.pair, b1.c, b1.c, b1.c))
        if not b5:
            continue
        bars_5m += 1

        cnt = pair_5m_count.get(b5.pair, 0) + 1
        pair_5m_count[b5.pair] = cnt

        if cnt < cfg.min_5m_bars_for_allow:
            regime_block += 1
            continue
        regime_allow += 1

        carry = compute_carry_and_forward(b5.pair, b5.c, cfg.rate_table, cfg.derivs, 1)

        # --- SANITY PROBE (EPSILON TEST) ---
        DIAG_EPSILON = 0.0001
        if abs(b5.c - b5.vwap) < DIAG_EPSILON:
            continue
        # ----------------------------------

        prompts.append(pg.build(b5, carry))

    os.makedirs(os.path.dirname(cfg.prompts_out), exist_ok=True)
    with open(cfg.prompts_out, "w", encoding="utf-8") as f:
        for p in prompts:
            f.write(p.text + "\n" + "-" * 72 + "\n")

    return {
        "bars_1m": bars_1m,
        "bars_5m": bars_5m,
        "regime_allow": regime_allow,
        "regime_block": regime_block,
        "prompts_generated": len(prompts),
    }


def main() -> int:
    cfg = RunnerConfig(csv_path=os.environ.get("REA_FX_CSV", "data/fx_pairs.csv"))
    stats = run(cfg)
    print("\nREA FX Runner Summary")
    print("-" * 72)
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("-" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())