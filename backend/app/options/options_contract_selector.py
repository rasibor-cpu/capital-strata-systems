from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class OptionContract:
    symbol: str
    option_type: str
    strike: float
    expiry_days: int
    premium: float
    moneyness: str


class OptionsContractSelector:
    """
    CSS Options Sandbox Phase 1:
    Selects candidate long CALL / PUT contracts.

    Supported underlyings:
        - SPY
        - QQQ
        - AAPL
    """

    SUPPORTED_UNDERLYINGS = {"SPY", "QQQ", "AAPL"}

    def __init__(self):
        pass

    def generate_candidate_contracts(
        self,
        symbol: str,
        spot_price: float,
        option_type: str,
    ) -> List[OptionContract]:

        symbol = symbol.upper()
        option_type = option_type.upper()

        if symbol not in self.SUPPORTED_UNDERLYINGS:
            raise ValueError(f"Unsupported underlying: {symbol}")

        if option_type not in {"CALL", "PUT"}:
            raise ValueError("option_type must be CALL or PUT")

        strikes = [
            round(spot_price * 0.95, 2),
            round(spot_price, 2),
            round(spot_price * 1.05, 2),
        ]

        expiries = [7, 14, 30]

        contracts = []

        for strike in strikes:
            for expiry in expiries:

                if strike < spot_price:
                    moneyness = "ITM"
                elif strike > spot_price:
                    moneyness = "OTM"
                else:
                    moneyness = "ATM"

                premium = round(
                    max(1.0, abs(spot_price - strike) * 0.15 + expiry * 0.08),
                    2
                )

                contracts.append(
                    OptionContract(
                        symbol=symbol,
                        option_type=option_type,
                        strike=strike,
                        expiry_days=expiry,
                        premium=premium,
                        moneyness=moneyness,
                    )
                )

        return contracts
