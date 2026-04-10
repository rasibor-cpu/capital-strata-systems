from __future__ import annotations

from typing import Dict, List, Any


def safe(v, d=0.0):
    try:
        return float(v)
    except:
        return d


class OptionsIntelligenceEngine:
    """
    CSS Options Intelligence Engine

    Purpose:
    - Select best option contracts
    - Filter bad contracts
    - Apply tier-aware logic
    - Improve profitability
    """

    def __init__(self):
        pass

    # =========================
    # MAIN ENTRY
    # =========================
    def select_best_option(
        self,
        *,
        options: List[Dict[str, Any]],
        underlying_price: float,
        score: float,
        tier: str
    ) -> Dict[str, Any] | None:

        if not options:
            return None

        # --- FILTER BAD OPTIONS ---
        valid = [
            o for o in options
            if self._is_valid_option(o)
        ]

        if not valid:
            return None

        # --- APPLY TIER STRATEGY ---
        ranked = sorted(
            valid,
            key=lambda o: self._score_option(o, underlying_price, score, tier),
            reverse=True
        )

        return ranked[0] if ranked else None

    # =========================
    # VALIDATION
    # =========================
    def _is_valid_option(self, o: Dict[str, Any]) -> bool:
        price = safe(o.get("price"))
        strike = safe(o.get("strike"))

        if price <= 0:
            return False

        if strike <= 0:
            return False

        return True

    # =========================
    # SCORING
    # =========================
    def _score_option(
        self,
        o: Dict[str, Any],
        underlying_price: float,
        signal_score: float,
        tier: str
    ) -> float:

        strike = safe(o.get("strike"))
        premium = safe(o.get("price"))

        if underlying_price <= 0:
            return 0.0

        # --- DISTANCE FROM ATM ---
        distance = abs(strike - underlying_price) / underlying_price

        # --- ATM PREFERENCE ---
        if tier == "ELITE":
            atm_penalty = distance * 2.0
        elif tier == "QUALIFIED":
            atm_penalty = distance * 3.0
        else:
            atm_penalty = distance * 5.0

        # --- PREMIUM PENALTY ---
        premium_penalty = premium * 2.0

        # --- SIGNAL BOOST ---
        signal_boost = signal_score / 10.0

        score = signal_boost - atm_penalty - premium_penalty

        return score