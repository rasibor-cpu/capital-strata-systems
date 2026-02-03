"""
REA Capital Trading Engine
Slippage Guard (Execution Control – Layer 5)

Constitutional Authority:
- Layer 5: Execution Control
- This module has ABSOLUTE VETO power
- It never improves price, retries orders, or adapts

Doctrine:
- Slippage must be bounded BEFORE execution
- Breach = CANCEL
- Uncertainty = NO EXECUTION
"""

from dataclasses import dataclass
from typing import Optional
import time


# -----------------------------
# Decision Object (Immutable)
# -----------------------------
@dataclass(frozen=True)
class SlippageDecision:
    allow: bool
    expected_price: float
    max_allowed_price: float
    actual_price: Optional[float]
    reason: str
    timestamp: float


# -----------------------------
# Slippage Guard
# -----------------------------
class SlippageGuard:
    """
    SlippageGuard enforces price reality discipline.
    It compares expected vs actual prices and vetoes execution
    if tolerance is breached.
    """

    def __init__(self, max_slippage_pct: float):
        """
        max_slippage_pct: e.g. 0.001 = 0.10%
        """
        if max_slippage_pct <= 0:
            raise ValueError("max_slippage_pct must be positive")

        self.max_slippage_pct = max_slippage_pct

    # -------------------------
    # Pre-Execution Check
    # -------------------------
    def pre_check(self, expected_price: float) -> SlippageDecision:
        """
        Called BEFORE sending an order.
        Establishes the maximum acceptable execution price.
        """
        ts = time.time()

        if expected_price <= 0:
            return self._block(
                expected_price,
                None,
                "Invalid expected price",
                ts,
            )

        max_price = expected_price * (1 + self.max_slippage_pct)

        return SlippageDecision(
            allow=True,
            expected_price=expected_price,
            max_allowed_price=max_price,
            actual_price=None,
            reason="Slippage bounds established",
            timestamp=ts,
        )

    # -------------------------
    # Post-Execution Check
    # -------------------------
    def post_check(
        self,
        expected_price: float,
        actual_price: Optional[float],
    ) -> SlippageDecision:
        """
        Called AFTER a fill (real or simulated).
        """
        ts = time.time()

        if actual_price is None:
            return self._block(
                expected_price,
                actual_price,
                "Missing actual execution price",
                ts,
            )

        max_price = expected_price * (1 + self.max_slippage_pct)

        if actual_price > max_price:
            return self._block(
                expected_price,
                actual_price,
                f"Slippage breach (actual={actual_price}, max={max_price})",
                ts,
            )

        return SlippageDecision(
            allow=True,
            expected_price=expected_price,
            max_allowed_price=max_price,
            actual_price=actual_price,
            reason="Execution within slippage tolerance",
            timestamp=ts,
        )

    # -------------------------
    # Internal Helper
    # -------------------------
    def _block(
        self,
        expected_price: float,
        actual_price: Optional[float],
        reason: str,
        ts: float,
    ) -> SlippageDecision:
        max_price = (
            expected_price * (1 + self.max_slippage_pct)
            if expected_price > 0
            else 0.0
        )

        return SlippageDecision(
            allow=False,
            expected_price=expected_price,
            max_allowed_price=max_price,
            actual_price=actual_price,
            reason=reason,
            timestamp=ts,
        )


# -----------------------------
# Constitutional Assertion
# -----------------------------
if __name__ == "__main__":
    raise RuntimeError(
        "SlippageGuard is a control module only. "
        "It cannot be executed standalone."
    )
