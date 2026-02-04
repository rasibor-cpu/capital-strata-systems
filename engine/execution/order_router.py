"""
Order Router – REA Capital Trading Engine
----------------------------------------

Purpose:
- Central routing point before any order execution.
- Now includes Slippage Guard as a mandatory pre-execution safety check.
- Designed to be NON-INTRUSIVE to adapters and execution venues.

Key Principles:
- No adapter logic here
- No broker-specific logic
- Hard-fail safe by default
- Human override respected where policy allows

"""

from __future__ import annotations

from typing import Dict, Any, Optional
from dataclasses import dataclass

from engine.execution.slippage_guard import (
    evaluate_slippage,
    SlippagePolicy,
    Side,
    SlippageResult,
)


@dataclass
class OrderIntent:
    symbol: str
    side: Side
    quantity: float
    expected_price: float
    venue: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RoutedOrder:
    allowed: bool
    reason: str
    slippage: Optional[SlippageResult]
    intent: OrderIntent


class OrderRouter:
    """
    Governance-aware order router.

    Flow:
    1. Receive OrderIntent
    2. Run slippage guard
    3. BLOCK or ALLOW
    4. Adapter executes only if allowed == True
    """

    def __init__(self, slippage_policy: Optional[SlippagePolicy] = None):
        self.slippage_policy = slippage_policy or SlippagePolicy()

    def route(self, intent: OrderIntent, fill_price_preview: float) -> RoutedOrder:
        """
        Main routing decision point.

        fill_price_preview:
        - Latest tradable price (quote / last / simulated fill)
        - Passed in from caller (strategy or adapter pre-check)
        """

        # --- Slippage Guard ---
        slippage_result = evaluate_slippage(
            expected_price=intent.expected_price,
            fill_price=fill_price_preview,
            side=intent.side,
            policy=self.slippage_policy,
            metadata={
                "symbol": intent.symbol,
                "venue": intent.venue,
            },
        )

        if not slippage_result.ok:
            return RoutedOrder(
                allowed=False,
                reason=slippage_result.reason,
                slippage=slippage_result,
                intent=intent,
            )

        # --- Passed all checks ---
        return RoutedOrder(
            allowed=True,
            reason="ORDER_ROUTER: OK",
            slippage=slippage_result,
            intent=intent,
        )
