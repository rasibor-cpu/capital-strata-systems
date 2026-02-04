"""
Liquidity Gate – REA Capital Trading Engine
-------------------------------------------

Purpose:
- Block trades when liquidity conditions are poor, spreads are too wide,
  or order size is too large relative to recent volume.
- Adapter-agnostic: callers pass in the market snapshot they have.
- Safe default: if required fields are missing, the gate BLOCKS.

Design notes:
- FX/crypto/equities/options supported generically via snapshot inputs.
- Works with "expected order notional" and basic spread/volume metrics.
- Produces a structured decision + reason string for audit logs.

Integration later:
- Called from strategy loop (pre-intent) and/or from router (pre-exec).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any


class LiquidityDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    WARN = "WARN"


@dataclass(frozen=True)
class LiquidityPolicy:
    """
    max_spread_bps: Maximum allowed spread in bps (bid-ask) / mid * 10,000
    max_notional_to_volume: Maximum fraction of recent volume you can consume
                            e.g. 0.02 means 2% of recent (e.g., 1m or 5m) volume.
    min_recent_volume: Minimum recent volume required (units depend on venue snapshot).
    hard_block: If True, failing any check blocks.
    """
    max_spread_bps: float = 35.0
    max_notional_to_volume: float = 0.02
    min_recent_volume: float = 0.0
    hard_block: bool = True
    reason_prefix: str = "LIQUIDITY_GATE"


@dataclass(frozen=True)
class LiquiditySnapshot:
    """
    A minimal market snapshot supplied by the caller/adapters.

    bid/ask: current best prices (if available)
    mid: optional precomputed mid price (if bid/ask missing)
    last: optional last trade price (fallback reference)
    recent_volume: recent traded volume (e.g., last 1m/5m). Can be notional or units,
                   but policy expects consistency with order_notional.
    """
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    last: Optional[float] = None
    recent_volume: Optional[float] = None
    venue: Optional[str] = None
    symbol: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class LiquidityResult:
    decision: LiquidityDecision
    spread_bps: Optional[float]
    notional_to_volume: Optional[float]
    reason: str


def _is_num(x) -> bool:
    return isinstance(x, (int, float))


def _validate_positive(x: float, name: str) -> None:
    if not _is_num(x):
        raise TypeError(f"{name} must be a number, got {type(x)}")
    if x <= 0:
        raise ValueError(f"{name} must be > 0, got {x}")


def _compute_mid(snapshot: LiquiditySnapshot) -> Optional[float]:
    if _is_num(snapshot.mid) and snapshot.mid and snapshot.mid > 0:
        return float(snapshot.mid)
    if _is_num(snapshot.bid) and _is_num(snapshot.ask):
        if snapshot.bid and snapshot.ask and snapshot.bid > 0 and snapshot.ask > 0:
            return (float(snapshot.bid) + float(snapshot.ask)) / 2.0
    if _is_num(snapshot.last) and snapshot.last and snapshot.last > 0:
        return float(snapshot.last)
    return None


def compute_spread_bps(snapshot: LiquiditySnapshot) -> Optional[float]:
    """
    spread_bps = (ask - bid) / mid * 10,000
    Returns None if insufficient data.
    """
    if not (_is_num(snapshot.bid) and _is_num(snapshot.ask)):
        return None
    bid = float(snapshot.bid)
    ask = float(snapshot.ask)
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = _compute_mid(snapshot)
    if not mid or mid <= 0:
        return None
    return (ask - bid) / mid * 10000.0


def evaluate_liquidity(
    *,
    snapshot: LiquiditySnapshot,
    order_notional: float,
    policy: LiquidityPolicy = LiquidityPolicy(),
) -> LiquidityResult:
    """
    Decide whether liquidity is sufficient for the proposed order_notional.

    Safe-default behavior:
    - If order_notional invalid => BLOCK.
    - If mid price missing => BLOCK.
    - If recent_volume missing => BLOCK (unless policy.min_recent_volume == 0 and
      policy.max_notional_to_volume is None-ish; but we keep it strict).
    """
    try:
        _validate_positive(order_notional, "order_notional")
    except Exception as e:
        return LiquidityResult(
            decision=LiquidityDecision.BLOCK,
            spread_bps=None,
            notional_to_volume=None,
            reason=f"{policy.reason_prefix}: BLOCK — invalid order_notional ({e}).",
        )

    mid = _compute_mid(snapshot)
    if not mid:
        return LiquidityResult(
            decision=LiquidityDecision.BLOCK,
            spread_bps=None,
            notional_to_volume=None,
            reason=f"{policy.reason_prefix}: BLOCK — missing reference price (mid/last).",
        )

    spread_bps = compute_spread_bps(snapshot)

    # Volume checks (strict)
    if snapshot.recent_volume is None or not _is_num(snapshot.recent_volume):
        return LiquidityResult(
            decision=LiquidityDecision.BLOCK,
            spread_bps=spread_bps,
            notional_to_volume=None,
            reason=f"{policy.reason_prefix}: BLOCK — missing recent_volume in snapshot.",
        )

    recent_vol = float(snapshot.recent_volume)
    if recent_vol < 0:
        return LiquidityResult(
            decision=LiquidityDecision.BLOCK,
            spread_bps=spread_bps,
            notional_to_volume=None,
            reason=f"{policy.reason_prefix}: BLOCK — invalid recent_volume (<0).",
        )

    if recent_vol < policy.min_recent_volume:
        return LiquidityResult(
            decision=LiquidityDecision.BLOCK if policy.hard_block else LiquidityDecision.WARN,
            spread_bps=spread_bps,
            notional_to_volume=(order_notional / recent_vol) if recent_vol > 0 else None,
            reason=(
                f"{policy.reason_prefix}: {'BLOCK' if policy.hard_block else 'WARN'} — "
                f"recent_volume {recent_vol:.6g} below minimum {policy.min_recent_volume:.6g}."
            ),
        )

    notional_to_volume = None
    if recent_vol > 0:
        notional_to_volume = order_notional / recent_vol
    else:
        # recent_vol == 0 => cannot trade safely
        return LiquidityResult(
            decision=LiquidityDecision.BLOCK,
            spread_bps=spread_bps,
            notional_to_volume=None,
            reason=f"{policy.reason_prefix}: BLOCK — recent_volume is zero.",
        )

    # Spread gate (if available)
    if spread_bps is not None and spread_bps > policy.max_spread_bps:
        action = "BLOCK" if policy.hard_block else "WARN"
        return LiquidityResult(
            decision=LiquidityDecision.BLOCK if policy.hard_block else LiquidityDecision.WARN,
            spread_bps=spread_bps,
            notional_to_volume=notional_to_volume,
            reason=(
                f"{policy.reason_prefix}: {action} — spread {spread_bps:.2f} bps "
                f"exceeds limit {policy.max_spread_bps:.2f} bps."
            ),
        )

    # Size vs volume gate
    if notional_to_volume > policy.max_notional_to_volume:
        action = "BLOCK" if policy.hard_block else "WARN"
        return LiquidityResult(
            decision=LiquidityDecision.BLOCK if policy.hard_block else LiquidityDecision.WARN,
            spread_bps=spread_bps,
            notional_to_volume=notional_to_volume,
            reason=(
                f"{policy.reason_prefix}: {action} — order_notional consumes "
                f"{(notional_to_volume*100):.2f}% of recent volume; "
                f"limit {(policy.max_notional_to_volume*100):.2f}%."
            ),
        )

    return LiquidityResult(
        decision=LiquidityDecision.ALLOW,
        spread_bps=spread_bps,
        notional_to_volume=notional_to_volume,
        reason=f"{policy.reason_prefix}: ALLOW — liquidity OK.",
    )


def quick_self_test() -> None:
    snap = LiquiditySnapshot(bid=99.90, ask=100.10, recent_volume=1_000_000, venue="SIM", symbol="TEST")
    pol = LiquidityPolicy(max_spread_bps=35.0, max_notional_to_volume=0.02, hard_block=True)

    r1 = evaluate_liquidity(snapshot=snap, order_notional=10_000, policy=pol)
    r2 = evaluate_liquidity(snapshot=snap, order_notional=50_000, policy=pol)  # 5% => block
    print(r1)
    print(r2)


if __name__ == "__main__":
    quick_self_test()
