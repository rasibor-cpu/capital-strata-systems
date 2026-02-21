"""
engine/regime/regime_classifier.py

Institutional Regime Classifier for CSS

Classifies each 5m bar into:
- TRENDING_UP
- TRENDING_DOWN
- MEAN_REVERTING
- NEUTRAL
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import pandas as pd


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period, min_periods=period).mean()


# ------------------------------------------------------------
# Regime Enum (simple string-based for portability)
# ------------------------------------------------------------

TRENDING_UP = "TRENDING_UP"
TRENDING_DOWN = "TRENDING_DOWN"
MEAN_REVERTING = "MEAN_REVERTING"
NEUTRAL = "NEUTRAL"


# ------------------------------------------------------------
# Classifier
# ------------------------------------------------------------

@dataclass
class RegimeConfig:
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    atr_lookback: int = 3
    slope_lookback: int = 3


def classify_regime(df_5m: pd.DataFrame, config: RegimeConfig = RegimeConfig()) -> pd.Series:

    close = df_5m["close"]

    ema_fast = _ema(close, config.ema_fast)
    ema_slow = _ema(close, config.ema_slow)

    atr = _atr(df_5m, config.atr_period)
    atr_mean = atr.rolling(config.atr_lookback).mean()

    # Slope approximation
    slope = ema_fast - ema_fast.shift(config.slope_lookback)

    regime = pd.Series(NEUTRAL, index=df_5m.index)

    trending_up = (
        (ema_fast > ema_slow) &
        (slope > 0) &
        (atr > atr_mean)
    )

    trending_down = (
        (ema_fast < ema_slow) &
        (slope < 0) &
        (atr > atr_mean)
    )

    mean_reverting = (
        (abs(ema_fast - ema_slow) < (0.1 * atr)) &
        (atr <= atr_mean)
    )

    regime[trending_up] = TRENDING_UP
    regime[trending_down] = TRENDING_DOWN
    regime[mean_reverting] = MEAN_REVERTING

    return regime