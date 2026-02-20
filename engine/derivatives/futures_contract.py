"""
FuturesContract – Canonical Futures Instrument Model
Capital Strata Systems (CSS)

Purpose:
- Define contract multiplier
- Define tick size
- Define tick value
- Provide standardized PnL computation

This is execution-neutral.
No broker dependency.
Pure structural layer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FuturesContract:
    symbol: str
    contract_multiplier: float
    tick_size: float
    tick_value: float

    # --------------------------------------------------

    def pnl(
        self,
        entry_price: float,
        exit_price: float,
        contracts: int,
        side: str,
    ) -> float:
        """
        Computes futures PnL.

        side: "LONG" or "SHORT"
        """

        if contracts <= 0:
            return 0.0

        price_diff = exit_price - entry_price

        if side.upper() == "SHORT":
            price_diff = -price_diff

        return price_diff * self.contract_multiplier * contracts


# --------------------------------------------------
# Canonical Contract Registry (Phase 1)
# --------------------------------------------------

ES = FuturesContract(
    symbol="ES",
    contract_multiplier=50.0,
    tick_size=0.25,
    tick_value=12.50,
)

NQ = FuturesContract(
    symbol="NQ",
    contract_multiplier=20.0,
    tick_size=0.25,
    tick_value=5.00,
)

CL = FuturesContract(
    symbol="CL",
    contract_multiplier=1000.0,
    tick_size=0.01,
    tick_value=10.00,
)

FUTURES_REGISTRY = {
    "ES": ES,
    "NQ": NQ,
    "CL": CL,
}
