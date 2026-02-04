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
                   e.g. 2.5 = current vol <= 2.5x baseline.
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
    return isinstance(x, (int, float))


def evaluate_volatility(
    *,
    snapshot: VolatilitySnapshot,
    policy: VolatilityPolicy = VolatilityPolicy(),
) -> VolatilityResult:
    """
    Evaluate whether current volatility is acceptable.

    Safe-default behavior:
    - Missing or invalid volatility data => BLOCK
    """

    if snapshot.current_vol is None or snapshot.baseline_vol is None:
        return VolatilityResult(
            decision=VolatilityDecision.BLOCK,
            vol_ratio=None,
            reason=f"{policy.reason_prefix}: BLOCK — missing volatility data.",
        )

    if not _is_num(snapshot.current_vol) or not _is_num(snapshot.baseline_vol):
        return VolatilityResult(
            decision=VolatilityDecision.BLOCK,
            vol_ratio=None,
            reason=f"{policy.reason_prefix}: BLOCK — non-numeric volatility data.",
        )

    current_vol = float(snapshot.current_vol)
    baseline_vol = float(snapshot.baseline_vol)

    if baseline_vol <= policy.min_baseline_vol:
        return VolatilityResult(
            decision=VolatilityDecision.BLOCK,
            vol_ratio=None,
            reason=(
                f"{policy.reason_prefix}: BLOCK — baseline volatility too low "
                f"({baseline_vol})."
            ),
        )

    if current_vol < 0:
        return VolatilityResult(
            decision=VolatilityDecision.BLOCK,
            vol_ratio=None,
            reason=f"{policy.reason_prefix}: BLOCK — invalid current volatility.",
        )

    vol_ratio = current_vol / baseline_vol

    if vol_ratio > policy.max_vol_ratio:
        action = "BLOCK" if policy.hard_block else "WARN"
        return VolatilityResult(
            decision=VolatilityDecision.BLOCK if policy.hard_block else VolatilityDecision.WARN,
            vol_ratio=vol_ratio,
            reason=(
                f"{policy.reason_prefix}: {action} — volatility ratio "
                f"{vol_ratio:.2f} exceeds limit {policy.max_vol_ratio:.2f}."
            ),
        )

    return VolatilityResult(
        decision=VolatilityDecision.ALLOW,
        vol_ratio=vol_ratio,
        reason=f"{policy.reason_prefix}: ALLOW — volatility within limits.",
    )


def quick_self_test() -> None:
    snap_ok = VolatilitySnapshot(current_vol=1.2, baseline_vol=1.0, symbol="TEST")
    snap_bad = VolatilitySnapshot(current_vol=3.5, baseline_vol=1.0, symbol="TEST")

    pol = VolatilityPolicy(max_vol_ratio=2.5, hard_block=True)

    r1 = evaluate_volatility(snapshot=snap_ok, policy=pol)
    r2 = evaluate_volatility(snapshot=snap_bad, policy=pol)

    print(r1)
    print(r2)


if __name__ == "__main__":
    quick_self_test()
