from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from data.models import Bar


@dataclass
class VolatilityPolicy:
    """
    5-minute volatility expansion filter.

    We compute:
      - recent realized volatility (std of returns)
      - prior realized volatility (std of returns)
    If recent/prior > expansion_ratio_threshold -> volatility expanding -> BLOCK.
    """
    recent_window: int = 12   # last 12 x 5m = 60 minutes
    prior_window: int = 12    # previous 60 minutes
    expansion_ratio_threshold: float = 1.35  # tune later


def _returns_from_closes(closes: List[float]) -> List[float]:
    rets = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        cur = closes[i]
        if prev <= 0:
            continue
        rets.append((cur - prev) / prev)
    return rets


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return var ** 0.5


def volatility_expansion_check(bars_5m: List[Bar], policy: VolatilityPolicy) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Returns:
      (is_expanding, reason_if_expanding, ratio)

    bars_5m: most recent bars in chronological order (oldest -> newest)
    """
    need = policy.recent_window + policy.prior_window + 1
    if len(bars_5m) < need:
        return True, "Insufficient 5m bars for volatility check.", None

    closes = [b.c for b in bars_5m]
    rets = _returns_from_closes(closes)

    # We want returns aligned with bars; use last (recent+prior) windows from returns list.
    # returns length = len(closes)-1
    if len(rets) < policy.recent_window + policy.prior_window:
        return True, "Insufficient returns for volatility check.", None

    recent = rets[-policy.recent_window:]
    prior = rets[-(policy.recent_window + policy.prior_window):-policy.recent_window]

    vol_recent = _std(recent)
    vol_prior = _std(prior)

    if vol_prior == 0:
        return True, "Prior volatility is zero/undefined; treat as unsafe.", None

    ratio = vol_recent / vol_prior
    if ratio > policy.expansion_ratio_threshold:
        return True, f"Volatility expanding: ratio {ratio:.2f} > {policy.expansion_ratio_threshold:.2f}", ratio

    return False, None, ratio
