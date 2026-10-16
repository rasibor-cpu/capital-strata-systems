"""Walk-forward calibration for EngineLoop MA-momentum signals (paper / research only).

Fits calibration parameters on the training fold only. Reports actual OOS metrics.
Failing strategies are not approved for routing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from backend.trading_profiles.engine_loop_calibration import (
    SCHEMA,
    STRATEGY_MA_MOMENTUM,
    CalibrationArtifact,
    save_calibration,
)
from backend.trading_profiles.market_bar_source import BarRecord
from backend.trading_profiles.strategy_enablement import StrategyEnablement

MA_WINDOW = 20
MIN_OOS_TRADES = 5
MAX_OOS_DRAWDOWN_PCT = 25.0


@dataclass(frozen=True)
class WalkForwardResult:
    artifact: CalibrationArtifact
    train_metrics: dict[str, Any]
    oos_metrics: dict[str, Any]
    approved: bool
    disable_reason: str | None


def _ma(prices: Sequence[float], window: int) -> float | None:
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / float(window)


def _simulate(
    closes: Sequence[float],
    *,
    fee_bps: float,
    spread_bps: float,
    slippage_bps: float,
    min_strength: float = 0.55,
) -> tuple[list[float], list[float]]:
    """Simple long-only MA momentum: enter when price > MA and strength high; exit on cross under.

    Returns (trade_pnls_bps_net, signal_strengths_at_entry).
    """
    cost = fee_bps + spread_bps + slippage_bps
    prices: list[float] = []
    pnls: list[float] = []
    strengths: list[float] = []
    position = 0  # 0 flat, 1 long
    entry = 0.0
    entry_strength = 0.0
    prev = None
    for close in closes:
        if close <= 0 or not math.isfinite(close):
            continue
        if prev is not None and prev > 0:
            ret = (close - prev) / prev
        else:
            ret = 0.0
        prices.append(close)
        ma = _ma(prices, MA_WINDOW)
        if ma is None:
            prev = close
            continue
        # strength proxy aligned with EngineLoop SignalEngine scale (0..1)
        momentum = (close - ma) / ma
        strength = max(0.0, min(1.0, abs(momentum) * 40.0))
        if position == 0 and close > ma and strength >= min_strength:
            position = 1
            entry = close
            entry_strength = strength
            strengths.append(strength)
        elif position == 1 and close < ma:
            gross_bps = ((close - entry) / entry) * 10_000.0
            pnls.append(gross_bps - cost)
            position = 0
        prev = close
    if position == 1 and entry > 0:
        gross_bps = ((closes[-1] - entry) / entry) * 10_000.0
        pnls.append(gross_bps - cost)
        if not strengths:
            strengths.append(entry_strength)
    return pnls, strengths


def _metrics(pnls: Sequence[float]) -> dict[str, Any]:
    if not pnls:
        return {
            "trade_count": 0,
            "win_rate": 0.0,
            "expectancy_bps": 0.0,
            "max_drawdown_pct": 0.0,
            "sum_pnl_bps": 0.0,
        }
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    wins = 0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = (peak - equity) / 100.0  # bps equity path -> rough pct points of cumulative bps/100
        max_dd = max(max_dd, dd)
        if p > 0:
            wins += 1
    return {
        "trade_count": len(pnls),
        "win_rate": wins / len(pnls),
        "expectancy_bps": sum(pnls) / len(pnls),
        "max_drawdown_pct": max_dd,
        "sum_pnl_bps": sum(pnls),
    }


def _fit_params(strengths: Sequence[float], pnls: Sequence[float]) -> tuple[float, float, float, float]:
    """Fit logistic / R14F mapping on train fold only. Conservative defaults if sparse."""
    if len(strengths) < 3 or len(pnls) < 3:
        # Conservative: require high strength; scores near Balanced R14F band when strong
        return (-2.0, 4.0, 10.0, 8.0)
    mean_s = sum(strengths) / len(strengths)
    win_rate = sum(1 for p in pnls if p > 0) / len(pnls)
    # Map mean strength to probability near observed win rate (clipped)
    # logistic(a + b*s) ≈ win_rate at s=mean_s with slope b≈4
    b = 4.0
    target = min(0.75, max(0.52, win_rate))
    # target = 1/(1+exp(-(a+b*mean_s))) => a = logit(target) - b*mean_s
    logit = math.log(target / (1.0 - target))
    a = logit - b * mean_s
    # signal_score around 12..17 for R14F: c0 + c1*s
    c1 = 8.0
    c0 = 11.0 + (win_rate - 0.5) * 4.0
    return (a, b, c0, c1)


def walk_forward_ma_momentum(
    bars: Sequence[BarRecord],
    *,
    train_frac: float = 0.6,
    fee_bps: float = 1.0,
    spread_bps: float = 1.0,
    slippage_bps: float = 1.0,
    version: str = "2026.10.16",
) -> WalkForwardResult:
    if len(bars) < MA_WINDOW * 4:
        artifact = CalibrationArtifact(
            schema=SCHEMA,
            version=version,
            strategy_id=STRATEGY_MA_MOMENTUM,
            a=0.0,
            b=0.0,
            c0=0.0,
            c1=0.0,
            min_strength=0.99,
            approved_for_routing=False,
            oos_metrics={"trade_count": 0, "reason": "insufficient_bars"},
            notes="insufficient bars for walk-forward",
        )
        return WalkForwardResult(artifact, {}, artifact.oos_metrics, False, "insufficient_bars")

    closes = [b.close for b in bars]
    split = max(MA_WINDOW * 2, int(len(closes) * train_frac))
    split = min(split, len(closes) - MA_WINDOW * 2)
    train, test = closes[:split], closes[split:]
    train_pnls, train_strengths = _simulate(
        train, fee_bps=fee_bps, spread_bps=spread_bps, slippage_bps=slippage_bps
    )
    oos_pnls, _ = _simulate(test, fee_bps=fee_bps, spread_bps=spread_bps, slippage_bps=slippage_bps)
    train_metrics = _metrics(train_pnls)
    oos_metrics = _metrics(oos_pnls)
    a, b, c0, c1 = _fit_params(train_strengths, train_pnls)

    approved = (
        oos_metrics["trade_count"] >= MIN_OOS_TRADES
        and oos_metrics["expectancy_bps"] > 0.0
        and oos_metrics["max_drawdown_pct"] < MAX_OOS_DRAWDOWN_PCT
    )
    reason = None
    if not approved:
        if oos_metrics["trade_count"] < MIN_OOS_TRADES:
            reason = "oos_trade_count_below_minimum"
        elif oos_metrics["expectancy_bps"] <= 0.0:
            reason = "oos_expectancy_non_positive_after_costs"
        else:
            reason = "oos_drawdown_exceeds_limit"

    # Quality inputs for bridge optional fields — derived from observed OOS only
    oos_metrics = {
        **oos_metrics,
        "replay_confidence": min(0.95, max(0.0, oos_metrics["win_rate"])) if approved else 0.0,
        "strategy_score": min(0.95, max(0.0, 0.5 + oos_metrics["expectancy_bps"] / 200.0)) if approved else 0.0,
        "fee_bps": fee_bps,
        "spread_bps": spread_bps,
        "slippage_bps": slippage_bps,
        "train_frac": train_frac,
        "bar_count": len(bars),
        "instrument": bars[0].instrument if bars else "",
        "source_id": bars[0].source_id if bars else "",
    }
    artifact = CalibrationArtifact(
        schema=SCHEMA,
        version=version,
        strategy_id=STRATEGY_MA_MOMENTUM,
        a=a,
        b=b,
        c0=c0,
        c1=c1,
        min_strength=0.55,
        approved_for_routing=approved,
        oos_metrics=oos_metrics,
        notes="walk-forward MA momentum; paper/research only; not a live-trading authorization",
    )
    return WalkForwardResult(artifact, train_metrics, oos_metrics, approved, reason)


def run_and_persist(
    bars: Sequence[BarRecord],
    *,
    artifact_path,
    enablement_root,
    **kwargs: Any,
) -> WalkForwardResult:
    result = walk_forward_ma_momentum(bars, **kwargs)
    save_calibration(artifact_path, result.artifact)
    registry = StrategyEnablement(enablement_root)
    if result.approved:
        registry.enable(
            result.artifact.strategy_id,
            reason="oos_walk_forward_passed",
            metrics=result.oos_metrics,
        )
    else:
        registry.disable(
            result.artifact.strategy_id,
            reason=result.disable_reason or "oos_walk_forward_failed",
            metrics=result.oos_metrics,
        )
    return result
