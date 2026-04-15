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

        self.min_volume_by_tier = {
            "ELITE": 25,
            "QUALIFIED": 15,
            "WATCH": 5,
            "DEFAULT": 10,
        }

        self.min_open_interest_by_tier = {
            "ELITE": 100,
            "QUALIFIED": 75,
            "WATCH": 25,
            "DEFAULT": 50,
        }

        self.max_spread_pct_by_tier = {
            "ELITE": 0.12,
            "QUALIFIED": 0.10,
            "WATCH": 0.08,
            "DEFAULT": 0.10,
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
            self._premium_cap_for_tier(normalized_tier, underlying_price)
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
                tier=normalized_tier,
            ):
                continue
            valid.append(dict(o))

        if not valid:
            return None

        valid = self._rank_option_candidates(
            options=valid,
            tier=normalized_tier,
            underlying_price=underlying_price,
            direction=normalized_direction or "CALL",
        )

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
        tier: str,
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

        bid = safe(o.get("bid"))
        ask = safe(o.get("ask"))
        volume = safe_int(o.get("volume"))
        open_interest = safe_int(o.get("open_interest", o.get("oi")))

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

        if volume < self._min_volume_for_tier(tier):
            return False

        if open_interest < self._min_open_interest_for_tier(tier):
            return False

        spread_pct = self._spread_pct(o)
        if spread_pct is None:
            return False

        if spread_pct > self._max_spread_pct_for_tier(tier):
            return False

        if bid > 0 and ask > 0 and ask < bid:
            return False

        return True

    # =========================================================
    # RANKING
    # =========================================================
    def _rank_option_candidates(
        self,
        *,
        options: List[Dict[str, Any]],
        tier: str,
        underlying_price: float,
        direction: str,
    ) -> List[Dict[str, Any]]:
        ranked = []
        for o in options:
            candidate = dict(o)
            candidate["candidate_score"] = self._score_candidate_option(
                option=candidate,
                tier=tier,
                underlying_price=underlying_price,
                direction=direction,
            )
            ranked.append(candidate)

        ranked.sort(
            key=lambda x: (
                safe(x.get("candidate_score")),
                -safe(x.get("days_to_expiry")),
            ),
            reverse=True,
        )
        return ranked

    def _score_candidate_option(
        self,
        *,
        option: Dict[str, Any],
        tier: str,
        underlying_price: float,
        direction: str,
    ) -> float:
        strike = safe(option.get("strike"))
        price = safe(option.get("price"))
        dte = safe_int(option.get("days_to_expiry"))
        delta = abs(safe(option.get("delta")))
        volume = safe_int(option.get("volume"))
        open_interest = safe_int(option.get("open_interest", option.get("oi")))
        spread_pct = self._spread_pct(option)

        target_delta = self._target_delta_for_tier(tier)

        moneyness_score = self._moneyness_score(strike, underlying_price)
        delta_score = self._delta_alignment_score(delta, target_delta)
        liquidity_score = self._liquidity_score(volume, open_interest)
        spread_score = self._spread_score(spread_pct)
        dte_score = self._dte_score(dte)
        premium_score = self._premium_efficiency_score(price, underlying_price)

        score = (
            moneyness_score * 0.28 +
            delta_score * 0.24 +
            spread_score * 0.18 +
            liquidity_score * 0.14 +
            dte_score * 0.08 +
            premium_score * 0.08
        )

        if direction not in {"CALL", "PUT"}:
            score -= 0.10

        return round(score, 6)

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

        delta_component = self._average_leg_delta_alignment_score(
            legs=legs,
            tier=tier,
        )

        spread_component = self._average_leg_spread_score(legs=legs)
        liquidity_component = self._average_leg_liquidity_score(legs=legs)

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
            delta_component * 0.60 +
            spread_component * 0.45 +
            liquidity_component * 0.35 +
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
            scores.append(self._moneyness_score(strike, underlying_price))

        if not scores:
            return 0.0

        return round(sum(scores) / len(scores), 6)

    def _average_leg_delta_alignment_score(
        self,
        *,
        legs: List[Dict[str, Any]],
        tier: str,
    ) -> float:
        if not legs:
            return 0.0

        target_delta = self._target_delta_for_tier(tier)
        scores = []

        for leg in legs:
            delta = abs(safe(leg.get("delta")))
            if delta <= 0:
                continue
            scores.append(self._delta_alignment_score(delta, target_delta))

        if not scores:
            return 0.0

        return round(sum(scores) / len(scores), 6)

    def _average_leg_spread_score(self, *, legs: List[Dict[str, Any]]) -> float:
        if not legs:
            return 0.0

        scores = []
        for leg in legs:
            spread_pct = self._spread_pct(leg)
            scores.append(self._spread_score(spread_pct))

        if not scores:
            return 0.0

        return round(sum(scores) / len(scores), 6)

    def _average_leg_liquidity_score(self, *, legs: List[Dict[str, Any]]) -> float:
        if not legs:
            return 0.0

        scores = []
        for leg in legs:
            volume = safe_int(leg.get("volume"))
            open_interest = safe_int(leg.get("open_interest", leg.get("oi")))
            scores.append(self._liquidity_score(volume, open_interest))

        if not scores:
            return 0.0

        return round(sum(scores) / len(scores), 6)

    # =========================================================
    # COMPONENT SCORERS
    # =========================================================
    def _moneyness_score(self, strike: float, underlying_price: float) -> float:
        if strike <= 0 or underlying_price <= 0:
            return 0.0

        distance = abs(strike - underlying_price) / underlying_price
        if distance <= 0.01:
            return 1.00
        if distance <= 0.02:
            return 0.90
        if distance <= 0.03:
            return 0.80
        if distance <= 0.05:
            return 0.65
        return 0.40

    def _delta_alignment_score(self, actual_delta: float, target_delta: float) -> float:
        if actual_delta <= 0 or target_delta <= 0:
            return 0.0

        diff = abs(actual_delta - target_delta)
        if diff <= 0.03:
            return 1.00
        if diff <= 0.06:
            return 0.90
        if diff <= 0.10:
            return 0.78
        if diff <= 0.15:
            return 0.62
        if diff <= 0.20:
            return 0.45
        return 0.25

    def _liquidity_score(self, volume: int, open_interest: int) -> float:
        volume = max(0, int(volume))
        open_interest = max(0, int(open_interest))

        if volume >= 200 and open_interest >= 500:
            return 1.00
        if volume >= 100 and open_interest >= 250:
            return 0.88
        if volume >= 50 and open_interest >= 150:
            return 0.76
        if volume >= 20 and open_interest >= 75:
            return 0.62
        if volume >= 10 and open_interest >= 50:
            return 0.48
        return 0.25

    def _spread_score(self, spread_pct: Optional[float]) -> float:
        if spread_pct is None:
            return 0.0
        if spread_pct <= 0.02:
            return 1.00
        if spread_pct <= 0.04:
            return 0.88
        if spread_pct <= 0.06:
            return 0.74
        if spread_pct <= 0.08:
            return 0.58
        if spread_pct <= 0.10:
            return 0.40
        return 0.20

    def _dte_score(self, dte: int) -> float:
        if dte <= 0:
            return 0.0
        if 7 <= dte <= 14:
            return 1.00
        if 5 <= dte <= 21:
            return 0.85
        if 22 <= dte <= 30:
            return 0.55
        return 0.25

    def _premium_efficiency_score(self, premium: float, underlying_price: float) -> float:
        if premium <= 0 or underlying_price <= 0:
            return 0.0

        ratio = premium / underlying_price
        if ratio <= 0.010:
            return 1.00
        if ratio <= 0.015:
            return 0.88
        if ratio <= 0.020:
            return 0.74
        if ratio <= 0.030:
            return 0.55
        return 0.30

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

    def _premium_cap_for_tier(self, tier: str, underlying_price: float) -> float:
        base_cap = float(self.tier_premium_caps.get(tier, self.tier_premium_caps["DEFAULT"]))
        if underlying_price <= 0:
            return base_cap

        dynamic_cap = underlying_price * 0.04
        return float(min(base_cap, max(100.0, dynamic_cap)))

    def _target_delta_for_tier(self, tier: str) -> float:
        return float(self.tier_delta_targets.get(tier, self.tier_delta_targets["DEFAULT"]))

    def _min_volume_for_tier(self, tier: str) -> int:
        return int(self.min_volume_by_tier.get(tier, self.min_volume_by_tier["DEFAULT"]))

    def _min_open_interest_for_tier(self, tier: str) -> int:
        return int(self.min_open_interest_by_tier.get(tier, self.min_open_interest_by_tier["DEFAULT"]))

    def _max_spread_pct_for_tier(self, tier: str) -> float:
        return float(self.max_spread_pct_by_tier.get(tier, self.max_spread_pct_by_tier["DEFAULT"]))

    def _spread_pct(self, o: Dict[str, Any]) -> Optional[float]:
        bid = safe(o.get("bid"), -1.0)
        ask = safe(o.get("ask"), -1.0)
        price = safe(o.get("price"), -1.0)

        if bid > 0 and ask > 0:
            if ask < bid:
                return None
            if ask == 0:
                return None
            return max(0.0, (ask - bid) / ask)

        if price > 0:
            return 0.05

        return None
