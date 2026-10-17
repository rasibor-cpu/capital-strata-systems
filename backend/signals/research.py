"""Features, approved strategies, costs, triple-barrier outcomes (no look-ahead).

Every feature at bar i uses data up to and including bar i only. Entries are taken at the
NEXT bar's open. When a stop and a target are both touched inside one bar the outcome is a
LOSS (conservative). All P&L is in basis points of entry, net of round-trip costs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from backend.signals.candles import Candle

APPROVED_STRATEGIES = ("TREND_BREAKOUT", "MEAN_REVERSION")


@dataclass(frozen=True)
class CostModel:
    """Per-side costs in bps. Defaults are conservative retail assumptions; the owner must
    confirm them against the actual broker fee schedule before any live use."""
    fee_bps: float
    spread_bps: float
    slippage_bps: float

    @property
    def round_trip_bps(self) -> float:
        # pay the fee on entry and exit, the spread once, slippage on entry and exit
        return 2 * self.fee_bps + self.spread_bps + 2 * self.slippage_bps


DEFAULT_COSTS: Mapping[str, CostModel] = {
    "CRYPTO": CostModel(fee_bps=60.0, spread_bps=5.0, slippage_bps=5.0),   # retail taker tier
    "FX": CostModel(fee_bps=0.0, spread_bps=1.5, slippage_bps=1.0),        # spread-only pricing
    # US equities on a commission-free broker still pay regulatory fees, spread and impact;
    # conservative for liquid ETFs on IEX-only data. Owner must confirm before any live use.
    "EQUITY": CostModel(fee_bps=0.5, spread_bps=3.0, slippage_bps=3.0),
}


@dataclass(frozen=True)
class Features:
    i: int
    close: float
    atr: float
    atr_pct: float
    vol_bps: float
    vol_percentile: float
    trend: float
    zscore: float
    breakout: int  # +1 up, -1 down, 0 none
    regime: str  # TRENDING | RANGING | HIGH_VOL


def _sma(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def compute_features(candles: Sequence[Candle], *, warmup: int = 200) -> list[Features | None]:
    """Features per bar (None during warm-up). O(n * window), deterministic."""
    out: list[Features | None] = []
    closes = [c.close for c in candles]
    trs: list[float] = []
    log_rets: list[float] = []
    ewma_var = 0.0
    vols: list[float] = []
    for i, c in enumerate(candles):
        prev_close = closes[i - 1] if i else c.open
        trs.append(max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close)))
        if i:
            r = math.log(c.close / prev_close)
            log_rets.append(r)
            ewma_var = 0.94 * ewma_var + 0.06 * r * r
        vols.append(math.sqrt(ewma_var) * 10_000)
        if i < warmup:
            out.append(None)
            continue
        atr = _sma(trs[i - 13:i + 1])
        sma20, sma50 = _sma(closes[i - 19:i + 1]), _sma(closes[i - 49:i + 1])
        std20 = math.sqrt(sum((x - sma20) ** 2 for x in closes[i - 19:i + 1]) / 20) or 1e-12
        prior_high = max(k.high for k in candles[i - 20:i])
        prior_low = min(k.low for k in candles[i - 20:i])
        window = vols[i - 199:i + 1]
        pct = sum(1 for v in window if v <= vols[i]) / len(window)
        atr_pct = atr / c.close
        trend = (sma20 - sma50) / c.close
        if pct > 0.9:
            regime = "HIGH_VOL"
        elif abs(trend) > 0.5 * atr_pct:
            regime = "TRENDING"
        else:
            regime = "RANGING"
        out.append(Features(i=i, close=c.close, atr=atr, atr_pct=atr_pct, vol_bps=vols[i], vol_percentile=pct,
                            trend=trend, zscore=(c.close - sma20) / std20,
                            breakout=1 if c.close > prior_high else (-1 if c.close < prior_low else 0), regime=regime))
    return out


@dataclass(frozen=True)
class Candidate:
    strategy: str
    side: str  # BUY | SELL
    score: float
    features: Features


def candidates_at(f: Features | None) -> list[Candidate]:
    """Approved strategy rules at one bar. Returns zero or more directional candidates."""
    if f is None or f.atr_pct <= 0:
        return []
    out = []
    if f.breakout and f.regime == "TRENDING" and (f.breakout > 0) == (f.trend > 0):
        out.append(Candidate("TREND_BREAKOUT", "BUY" if f.breakout > 0 else "SELL", abs(f.trend) / f.atr_pct, f))
    if f.regime == "RANGING" and abs(f.zscore) >= 2.0:
        out.append(Candidate("MEAN_REVERSION", "SELL" if f.zscore > 0 else "BUY", abs(f.zscore), f))
    return out


@dataclass(frozen=True)
class BarrierParams:
    stop_atr: float = 1.5
    reward_risk: float = 2.0
    horizon_bars: int = 24


@dataclass(frozen=True)
class Outcome:
    entry_index: int
    exit_index: int
    result: str  # WIN | LOSS | TIMEOUT
    gross_bps: float
    net_bps: float
    stop_distance_pct: float


def triple_barrier(candles: Sequence[Candle], cand: Candidate, params: BarrierParams, costs: CostModel) -> Outcome | None:
    """Enter at the next bar's open; first barrier touched wins; ties resolve to LOSS."""
    i = cand.features.i + 1
    if i >= len(candles):
        return None
    entry = candles[i].open
    d = 1 if cand.side == "BUY" else -1
    stop_dist = params.stop_atr * cand.features.atr
    stop = entry - d * stop_dist
    take = entry + d * stop_dist * params.reward_risk
    last = min(len(candles) - 1, i + params.horizon_bars - 1)
    result, exit_px, exit_i = "TIMEOUT", candles[last].close, last
    for j in range(i, last + 1):
        bar = candles[j]
        hit_stop = (bar.low <= stop) if d > 0 else (bar.high >= stop)
        hit_take = (bar.high >= take) if d > 0 else (bar.low <= take)
        if hit_stop:  # includes the both-touched case: conservative
            result, exit_px, exit_i = "LOSS", stop, j
            break
        if hit_take:
            result, exit_px, exit_i = "WIN", take, j
            break
    if result == "TIMEOUT" and last - i + 1 < params.horizon_bars:
        return None  # not enough future data to judge: excluded, never guessed
    gross = d * (exit_px - entry) / entry * 10_000
    return Outcome(i, exit_i, result, gross, gross - costs.round_trip_bps, stop_dist / entry * 100)


@dataclass
class Event:
    strategy: str
    side: str
    score: float
    regime: str
    entry_index: int
    exit_index: int
    net_bps: float
    win: bool
    extra: dict = field(default_factory=dict)


def label_events(candles: Sequence[Candle], params: BarrierParams, costs: CostModel) -> list[Event]:
    """All strategy candidates with their realized outcomes. One open trade per strategy at a time."""
    feats = compute_features(candles)
    busy_until: dict[str, int] = {}
    events: list[Event] = []
    for f in feats:
        for cand in candidates_at(f):
            if busy_until.get(cand.strategy, -1) >= cand.features.i:
                continue
            out = triple_barrier(candles, cand, params, costs)
            if out is None:
                continue
            busy_until[cand.strategy] = out.exit_index
            events.append(Event(cand.strategy, cand.side, cand.score, cand.features.regime, out.entry_index,
                                out.exit_index, out.net_bps, out.result == "WIN",
                                {"stop_distance_pct": out.stop_distance_pct, "gross_bps": out.gross_bps}))
    return events
