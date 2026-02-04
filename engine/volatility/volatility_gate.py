"""
Volatility Gate – REA Capital Trading Engine
--------------------------------------------

Purpose:
- Block trades during abnormal or dangerous volatility regimes.
- Adapter-agnostic: caller supplies volatility snapshot (ATR, stdev, VIX-like proxy).
- Safe default: missing or invalid volatility data => BLOCK.

Design:
- Supports FX, crypto, equities, options via generic metrics.
- Volatility is evaluated relative to recent baseline.
- Produces structured decision + reason for audit trails.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any


class VolatilityDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    WARN = "WARN"


@dataclass(frozen=True)
class VolatilityPolicy:
    """
    max_vol_ratio: Maximum allowed ratio of current volatility
                   to recent baseline volatility.
                   e.g. 2.0 = current vol <= 2x baseline.
    min_baseline_vol: Minimum acceptable baseline volatility (>0).
    hard_block: If True, breaches block execution.
    """
    max_vol_ratio: float = 2.5
    min_baseline_vol: float = 1e-9
    hard_block: bool = True
    reason_prefix: str = "VOLATILITY_GATE"


@dataclass(frozen=True)
class VolatilitySnapshot:
    """
    Generic volatility snapshot.

    current_vol: current volatility metric (ATR, stdev, implied proxy, etc.)
    baseline_vol: recent baseline volatility (e.g., rolling mean).
    symbol: optional symbol
    venue: optional venue
    extra: optional metadata
    """
    current_vol: Optional[float]
    baseline_vol: Optional[float]
    symbol: Optional[str] = None
    venue: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class VolatilityResult:
    decision: VolatilityDecision
    vol_ratio: Optional[float]
    reason: str


def _is_num(x) -> bool:
    return isinstance
