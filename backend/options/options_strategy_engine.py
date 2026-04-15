from __future__ import annotations
from typing import Dict, List, Optional


class OptionStrategyEngine:
    """
    Phase-1 Full Stack Options Strategy Engine

    Live enabled:
    - LONG_CALL
    - LONG_PUT
    - CALL_DEBIT_SPREAD
    - PUT_DEBIT_SPREAD

    Scaffolded:
    - COVERED_CALL
    - CASH_SECURED_PUT
    """

    MIN_DEBIT_RR_THRESHOLD = 1.20

    def __init__(self):
        pass

    def build_strategy(
        self,
        *,
        option_chain: List[Dict],
        underlying_price: float,
        direction: str,
        tier: str
    ) -> Optional[Dict]:

        if not option_chain:
            return None

        if direction == "CALL":
            if tier == "ELITE":
                return self._build_call_debit_spread(option_chain, underlying_price)
            return self._build_long_call(option_chain, underlying_price)

        if direction == "PUT":
            if tier == "ELITE":
                return self._build_put_debit_spread(option_chain, underlying_price)
            return self._build_long_put(option_chain, underlying_price)

        return None

    # ---------------------------------------------------
    # LONG CALL
    # ---------------------------------------------------
    def _build_long_call(self, chain, underlying):
        calls = [x for x in chain if x["option_type"] == "CALL"]
        if not calls:
            return None

        best = min(calls, key=lambda x: abs(x["strike"] - underlying))

        return {
            "strategy": "LONG_CALL",
            "legs": [best],
            "max_loss": best["price"],
            "max_profit": "UNLIMITED",
            "breakeven": best["strike"] + best["price"]
        }

    # ---------------------------------------------------
    # LONG PUT
    # ---------------------------------------------------
    def _build_long_put(self, chain, underlying):
        puts = [x for x in chain if x["option_type"] == "PUT"]
        if not puts:
            return None

        best = min(puts, key=lambda x: abs(x["strike"] - underlying))

        max_profit = max(0.01, best["strike"] - best["price"])

        return {
            "strategy": "LONG_PUT",
            "legs": [best],
            "max_loss": best["price"],
            "max_profit": max_profit,
            "breakeven": best["strike"] - best["price"]
        }

    # ---------------------------------------------------
    # CALL DEBIT SPREAD
    # ---------------------------------------------------
    def _build_call_debit_spread(self, chain, underlying):
        calls = sorted(
            [x for x in chain if x["option_type"] == "CALL"],
            key=lambda x: x["strike"]
        )

        if len(calls) < 2:
            return self._build_long_call(chain, underlying)

        long_leg = min(calls, key=lambda x: abs(x["strike"] - underlying))
        higher = [x for x in calls if x["strike"] > long_leg["strike"]]

        if not higher:
            return self._build_long_call(chain, underlying)

        short_leg = higher[0]

        debit = long_leg["price"] - short_leg["price"]
        width = short_leg["strike"] - long_leg["strike"]

        if not self._valid_debit_structure(debit, width):
            return self._build_long_call(chain, underlying)

        max_profit = width - debit

        return {
            "strategy": "CALL_DEBIT_SPREAD",
            "legs": [long_leg, short_leg],
            "max_loss": debit,
            "max_profit": max_profit,
            "breakeven": long_leg["strike"] + debit
        }

    # ---------------------------------------------------
    # PUT DEBIT SPREAD
    # ---------------------------------------------------
    def _build_put_debit_spread(self, chain, underlying):
        puts = sorted(
            [x for x in chain if x["option_type"] == "PUT"],
            key=lambda x: x["strike"],
            reverse=True
        )

        if len(puts) < 2:
            return self._build_long_put(chain, underlying)

        long_leg = min(puts, key=lambda x: abs(x["strike"] - underlying))
        lower = [x for x in puts if x["strike"] < long_leg["strike"]]

        if not lower:
            return self._build_long_put(chain, underlying)

        short_leg = lower[0]

        debit = long_leg["price"] - short_leg["price"]
        width = long_leg["strike"] - short_leg["strike"]

        if not self._valid_debit_structure(debit, width):
            return self._build_long_put(chain, underlying)

        max_profit = width - debit

        return {
            "strategy": "PUT_DEBIT_SPREAD",
            "legs": [long_leg, short_leg],
            "max_loss": debit,
            "max_profit": max_profit,
            "breakeven": long_leg["strike"] - debit
        }

    # ---------------------------------------------------
    # VALIDATION HELPERS
    # ---------------------------------------------------
    def _valid_debit_structure(self, debit: float, width: float) -> bool:
        debit = float(debit)
        width = float(width)

        if debit <= 0:
            return False

        if width <= 0:
            return False

        max_profit = width - debit
        if max_profit <= 0:
            return False

        rr_ratio = max_profit / debit
        if rr_ratio < self.MIN_DEBIT_RR_THRESHOLD:
            return False

        return True
