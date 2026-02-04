"""
Slippage Guard (REA Capital – Trading Engine)

Goal:
- Prevent executions where realized slippage exceeds a policy threshold.
- Pure utility module (safe to add without touching existing adapters).
- Supports FX/crypto/equities/options in a generic way.

Usage pattern (integration later):
- Compute expected_price at decision time (quote/mid/last depending on venue).
- At order fill/confirm time, compare expected_price vs fill_price.
- If slippage_bps > max_bps => BLOCK (or require human override per governance).

No external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Tuple


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class SlippagePolicy:
    """
    max_bps: maximum allowed slippage in basis points (bps)
             10 bps = 0.10%, 50 bps = 0.50%
    hard_block: if True, slippage breach => block execution (default True)
    """
    max_bps: float = 25.0
    hard_block: bool = True
    reason_prefix: str = "SLIPPAGE_GUARD"


@dataclass(frozen=True)
class SlippageResult:
    ok: bool
    slippage_bps: float
    expected_price: float
    fill_price: float
    side: Side
    max_bps: float
    reason: str


def _validate_price(x: float, name: str) -> None:
    if x is None:
        raise ValueError(f"{name} is None")
    if not isinstance(x, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(x)}")
    if x <= 0:
        raise ValueError(f"{name} must be > 0, got {x}")


def compute_slippage_bps(expected_price: float, fill_price: float) -> float:
    """
    Slippage magnitude in bps relative to expected_price.
    Always non-negative.

    slippage_bps = abs(fill - expected) / expected * 10,000
    """
    _validate_price(expected_price, "expected_price")
    _validate_price(fill_price, "fill_price")
    return abs(fill_price - expected_price) / expected_price * 10000.0


def slippage_is_adverse(expected_price: float, fill_price: float, side: Side) -> bool:
    """
    Determine whether the fill is adverse vs expectation for the given side.
    BUY: higher fill is adverse
    SELL: lower fill is adverse
    """
    _validate_price(expected_price, "expected_price")
    _validate_price(fill_price, "fill_price")

    if side == Side.BUY:
        return fill_price > expected_price
    if side == Side.SELL:
        return fill_price < expected_price
    raise ValueError(f"Unknown side: {side}")


def evaluate_slippage(
    *,
    expected_price: float,
    fill_price: float,
    side: Side,
    policy: SlippagePolicy = SlippagePolicy(),
    metadata: Optional[Dict[str, Any]] = None,
) -> SlippageResult:
    """
    Returns SlippageResult with ok=True if slippage within limits OR non-adverse.

    Key design choice (loss-proof bias):
    - Only count slippage against you (adverse slippage).
    - Favorable slippage is allowed (but still measured and reported).
    """
    _validate_price(expected_price, "expected_price")
    _validate_price(fill_price, "fill_price")

    slip_bps = compute_slippage_bps(expected_price, fill_price)
    adverse = slippage_is_adverse(expected_price, fill_price, side)

    if not adverse:
        return SlippageResult(
            ok=True,
            slippage_bps=slip_bps,
            expected_price=expected_price,
            fill_price=fill_price,
            side=side,
            max_bps=policy.max_bps,
            reason=f"{policy.reason_prefix}: OK (favorable/non-adverse slippage).",
        )

    if slip_bps <= policy.max_bps:
        return SlippageResult(
            ok=True,
            slippage_bps=slip_bps,
            expected_price=expected_price,
            fill_price=fill_price,
            side=side,
            max_bps=policy.max_bps,
            reason=f"{policy.reason_prefix}: OK (adverse slippage within limit).",
        )

    # Breach
    meta_str = ""
    if metadata:
        # keep it compact
        kv = ", ".join([f"{k}={metadata.get(k)}" for k in sorted(metadata.keys())][:8])
        meta_str = f" meta[{kv}]"

    action = "BLOCK" if policy.hard_block else "WARN"
    return SlippageResult(
        ok=not policy.hard_block,
        slippage_bps=slip_bps,
        expected_price=expected_price,
        fill_price=fill_price,
        side=side,
        max_bps=policy.max_bps,
        reason=(
            f"{policy.reason_prefix}: {action} — adverse slippage {slip_bps:.2f} bps "
            f"exceeds limit {policy.max_bps:.2f} bps.{meta_str}"
        ),
    )


def quick_self_test() -> Tuple[SlippageResult, SlippageResult, SlippageResult]:
    """
    Minimal sanity checks you can run standalone.
    """
    pol = SlippagePolicy(max_bps=25.0, hard_block=True)

    # BUY adverse: expected 100, fill 100.20 => 20 bps OK
    r1 = evaluate_slippage(expected_price=100.0, fill_price=100.20, side=Side.BUY, policy=pol)

    # BUY adverse: expected 100, fill 100.50 => 50 bps BLOCK
    r2 = evaluate_slippage(expected_price=100.0, fill_price=100.50, side=Side.BUY, policy=pol)

    # SELL favorable: expected 100, fill 100.30 => favorable, OK
    r3 = evaluate_slippage(expected_price=100.0, fill_price=100.30, side=Side.SELL, policy=pol)

    return r1, r2, r3


if __name__ == "__main__":
    a, b, c = quick_self_test()
    print(a)
    print(b)
    print(c)
