from __future__ import annotations
from typing import Dict, List, Optional, Any

from backend.options.options_strategy_engine import OptionStrategyEngine
from backend.options.option_payoff_engine import OptionPayoffEngine
from backend.options.option_risk_profile_engine import OptionRiskProfileEngine


def safe(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def safe_int(v, d=0):
    try:
        return int(float(v))
    except Exception:
        return d


def safe_str(v, d=""):
    try:
        if v is None:
            return d
        return str(v).strip()
    except Exception:
        return d


class OptionsIntelligenceEngine:
    """
    Phase-1 Full Stack Options Intelligence Engine

    Live-enabled strategies:
    - LONG_CALL
    - LONG_PUT
    - CALL_DEBIT_SPREAD
    - PUT_DEBIT_SPREAD

    Scaffold-ready:
    - COVERED_CALL
    - CASH_SECURED_PUT
    """

    def __init__(self):
        self.strategy_engine = OptionStrategyEngine()
        self.payoff_engine = OptionPayoffEngine()
        self.risk_engine = OptionRiskProfileEngine()

        self.default_min_dte = 5
        self.default_max_dte = 21

        self.tier_premium_caps = {
            "ELITE": 500.0,
            "QUALIFIED": 350.0,
            "WATCH": 200.0,
            "DEFAULT": 250.0,
        }

        self.tier_delta_targets = {
            "ELITE": 0.55,
            "QUALIFIED": 0.50,
            "WATCH": 0.45,
            "DEFAULT": 0.50,
        }

    # =========================================================
    # PUBLIC ENTRY
    # =========================================================
    def select_best_option(
        self,
        *,
        options: List[Dict[str, Any]],
        underlying_price: float,
        score: float,
        tier: str,
        direction: Optional[str] = None,
        min_dte: Optional[int] = None,
        max_dte: Optional[int] = None,
        max_premium: Optional[float] = None,
    ) -> Dict[str, Any] | None:

        if not options:
            return None

        normalized_tier = self._normalize_tier(tier)
        normalized_direction = self._normalize_direction(direction)

        min_dte = self.default_min_dte if min_dte is None else int(min_dte)
        max_dte = self.default_max_dte if max_dte is None else int(max_dte)
        max_premium = (
            self._premium_cap_for_tier(normalized_tier)
            if max_premium is None
            else float(max_premium)
        )

        valid = []
        for o in options:
            if not self._is_valid_option(
                o,
                underlying_price=underlying_price,
                direction=normalized_direction,
                min_dte=min_dte,
                max_dte=max_dte,
                max_premium=max_premium,
            ):
                continue
            valid.append(dict(o))

        if not valid:
            return None

        strategy_payload = self.strategy_engine.build_strategy(
            option_chain=valid,
            underlying_price=underlying_price,
            direction=normalized_direction or "CALL",
            tier=normalized_tier,
        )

        if not strategy_payload:
            return None

        payoff = self.payoff_engine.calculate(strategy_payload)
        strategy_payload.update(payoff)

        risk_profile = self.risk_engine.evaluate(strategy_payload)
        strategy_payload.update(risk_profile)

        strategy_payload["selection_tier"] = normalized_tier
        strategy_payload["selection_direction"] = normalized_direction or "CALL"
        strategy_payload["underlying_price"] = underlying_price
        strategy_payload["signal_score"] = float(score)
        strategy_payload["strategy_score"] = self._score_strategy(
            strategy_payload=strategy_payload,
            signal_score=score,
            tier=normalized_tier,
            underlying_price=underlying_price,
        )

        strategy_payload["execution_ready"] = True
        strategy_payload["selected"] = True
        strategy_payload["selection_engine"] = "OptionsIntelligenceEngine"

        return strategy_payload

    # =========================================================
    # VALIDATION
    # =========================================================
    def _is_valid_option(
        self,
        o: Dict[str, Any],
        *,
        underlying_price: float,
        direction: Optional[str],
        min_dte: int,
        max_dte: int,
        max_premium: float,
    ) -> bool:
        price = safe(o.get("price"))
        strike = safe(o.get("strike"))
        option_type = self._normalize_direction(
            o.get("option_type", o.get("type"))
        )
        dte = safe_int(o.get("days_to_expiry"))
        delta = safe(o.get("delta"))
        symbol = safe_str(o.get("symbol"))
        expiry = safe_str(o.get("expiry"))

        if not symbol:
            return False

        if price <= 0 or price > max_premium:
            return False

        if strike <= 0 or underlying_price <= 0:
            return False

        if not expiry:
            return False

        if direction and option_type and option_type != direction:
            return False

        if option_type not in {"CALL", "PUT"}:
            return False

        if dte <= 0 or dte < min_dte or dte > max_dte:
            return False

        if option_type == "CALL" and delta <= 0:
            return False

        if option_type == "PUT" and delta >= 0:
            return False

        return True

    # =========================================================
    # STRATEGY SCORING
    # =========================================================
    def _score_strategy(
        self,
        *,
        strategy_payload: Dict[str, Any],
        signal_score: float,
        tier: str,
        underlying_price: float,
    ) -> float:
        strategy = safe_str(strategy_payload.get("strategy"))
        rr_ratio = strategy_payload.get("risk_reward_ratio", 0)
        max_loss = strategy_payload.get("max_loss", 0)
        legs = strategy_payload.get("legs", [])

        if rr_ratio == 9.99:
            rr_component = 2.0
        else:
            rr_component = min(safe(rr_ratio), 3.0)

        premium_component = 0.0
        if safe(max_loss) > 0:
            premium_component = max(0.0, 1.5 - min(safe(max_loss) / 100.0, 1.5))

        moneyness_component = self._average_leg_moneyness_score(
            legs=legs,
            underlying_price=underlying_price,
        )

        strategy_bonus = {
            "LONG_CALL": 0.40,
            "LONG_PUT": 0.40,
            "CALL_DEBIT_SPREAD": 0.65,
            "PUT_DEBIT_SPREAD": 0.65,
        }.get(strategy, 0.20)

        tier_bonus = {
            "ELITE": 0.35,
            "QUALIFIED": 0.20,
            "WATCH": 0.05,
            "DEFAULT": 0.10,
        }.get(tier, 0.10)

        score = (
            float(signal_score) * 0.35 +
            rr_component * 1.20 +
            premium_component * 0.90 +
            moneyness_component * 0.80 +
            strategy_bonus +
            tier_bonus
        )

        return round(score, 6)

    def _average_leg_moneyness_score(
        self,
        *,
        legs: List[Dict[str, Any]],
        underlying_price: float,
    ) -> float:
        if not legs or underlying_price <= 0:
            return 0.0

        scores = []
        for leg in legs:
            strike = safe(leg.get("strike"))
            if strike <= 0:
                continue

            distance = abs(strike - underlying_price) / underlying_price
            if distance <= 0.01:
                scores.append(1.00)
            elif distance <= 0.02:
                scores.append(0.90)
            elif distance <= 0.03:
                scores.append(0.80)
            elif distance <= 0.05:
                scores.append(0.65)
            else:
                scores.append(0.40)

        if not scores:
            return 0.0

        return round(sum(scores) / len(scores), 6)

    # =========================================================
    # HELPERS
    # =========================================================
    def _normalize_tier(self, tier: Any) -> str:
        t = safe_str(tier, "DEFAULT").upper()
        if t in {"ELITE", "QUALIFIED", "WATCH"}:
            return t
        return "DEFAULT"

    def _normalize_direction(self, direction: Any) -> Optional[str]:
        d = safe_str(direction, "").upper()
        if d in {"CALL", "PUT"}:
            return d
        return None

    def _premium_cap_for_tier(self, tier: str) -> float:
        return float(self.tier_premium_caps.get(tier, self.tier_premium_caps["DEFAULT"]))