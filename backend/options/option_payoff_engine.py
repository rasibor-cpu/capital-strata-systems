from __future__ import annotations
from typing import Dict


class OptionPayoffEngine:
    """
    Computes payoff characteristics for options strategies.
    Supports:
    - LONG_CALL
    - LONG_PUT
    - CALL_DEBIT_SPREAD
    - PUT_DEBIT_SPREAD
    """

    def __init__(self):
        pass

    def calculate(self, strategy_payload: Dict) -> Dict:
        strategy = strategy_payload.get("strategy")

        if strategy == "LONG_CALL":
            return self._long_call(strategy_payload)

        if strategy == "LONG_PUT":
            return self._long_put(strategy_payload)

        if strategy == "CALL_DEBIT_SPREAD":
            return self._call_debit_spread(strategy_payload)

        if strategy == "PUT_DEBIT_SPREAD":
            return self._put_debit_spread(strategy_payload)

        return {
            "max_profit": 0,
            "max_loss": 0,
            "breakeven": 0
        }

    # ----------------------------------------
    # LONG CALL
    # ----------------------------------------
    def _long_call(self, payload):
        leg = payload["legs"][0]

        premium = leg["price"]
        strike = leg["strike"]

        return {
            "max_profit": "UNLIMITED",
            "max_loss": premium,
            "breakeven": strike + premium
        }

    # ----------------------------------------
    # LONG PUT
    # ----------------------------------------
    def _long_put(self, payload):
        leg = payload["legs"][0]

        premium = leg["price"]
        strike = leg["strike"]

        return {
            "max_profit": strike,
            "max_loss": premium,
            "breakeven": strike - premium
        }

    # ----------------------------------------
    # CALL DEBIT SPREAD
    # ----------------------------------------
    def _call_debit_spread(self, payload):
        long_leg = payload["legs"][0]
        short_leg = payload["legs"][1]

        debit = long_leg["price"] - short_leg["price"]
        width = short_leg["strike"] - long_leg["strike"]

        return {
            "max_profit": width - debit,
            "max_loss": debit,
            "breakeven": long_leg["strike"] + debit
        }

    # ----------------------------------------
    # PUT DEBIT SPREAD
    # ----------------------------------------
    def _put_debit_spread(self, payload):
        long_leg = payload["legs"][0]
        short_leg = payload["legs"][1]

        debit = long_leg["price"] - short_leg["price"]
        width = long_leg["strike"] - short_leg["strike"]

        return {
            "max_profit": width - debit,
            "max_loss": debit,
            "breakeven": long_leg["strike"] - debit
        }