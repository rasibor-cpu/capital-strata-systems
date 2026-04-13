from __future__ import annotations

from typing import Dict, List, Any, Optional

from backend.intelligence.probability_prediction_engine import ProbabilityPredictionEngine


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
    CSS Options Intelligence Engine

    Purpose:
    - Select best option contracts
    - Filter bad contracts
    - Apply tier-aware logic
    - Improve profitability
    - Remain backward-compatible with earlier CSS options flow

    Current upgrade adds:
    - Optional CALL / PUT directional filtering
    - DTE window filtering
    - Premium cap filtering
    - Delta-aware ranking
    - Moneyness-aware ranking
    - Execution-ready output packaging
    - Pre-trade probability scoring

    Backward compatibility:
    Existing calls like:
        select_best_option(options=..., underlying_price=..., score=..., tier=...)
    still work unchanged.
    """

    def __init__(self):
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

        self.tier_probability_thresholds = {
            "ELITE": 0.70,
            "QUALIFIED": 0.62,
            "WATCH": 0.55,
            "DEFAULT": 0.55,
        }

        self.probability_engine = ProbabilityPredictionEngine()

    # =========================
    # MAIN ENTRY
    # =========================
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
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | None:

        if not options:
            return None

        normalized_tier = self._normalize_tier(tier)
        normalized_direction = self._normalize_direction(direction)
        context = context or {}

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

            probability_result = self._estimate_probability(
                option=o,
                score=score,
                tier=normalized_tier,
                direction=normalized_direction,
                context=context,
            )

            min_probability = self.tier_probability_thresholds.get(
                normalized_tier, self.tier_probability_thresholds["DEFAULT"]
            )

            if safe(probability_result.get("win_probability")) < min_probability:
                continue

            enriched = dict(o)
            enriched.update(probability_result)
            valid.append(enriched)

        if not valid:
            return None

        ranked = sorted(
            valid,
            key=lambda o: self._score_option(
                o=o,
                underlying_price=underlying_price,
                signal_score=score,
                tier=normalized_tier,
                direction=normalized_direction,
            ),
            reverse=True,
        )

        best = ranked[0] if ranked else None
        if not best:
            return None

        return self._build_selection_payload(
            option=best,
            underlying_price=underlying_price,
            signal_score=score,
            tier=normalized_tier,
            direction=normalized_direction,
            rank_score=self._score_option(
                o=best,
                underlying_price=underlying_price,
                signal_score=score,
                tier=normalized_tier,
                direction=normalized_direction,
            ),
        )

    # =========================
    # VALIDATION
    # =========================
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
        option_type = self._normalize_direction(o.get("option_type"))
        dte = safe_int(o.get("days_to_expiry"))
        delta = safe(o.get("delta"))
        symbol = safe_str(o.get("symbol"))

        if not symbol:
            return False

        if price <= 0:
            return False

        if strike <= 0:
            return False

        if underlying_price <= 0:
            return False

        if direction and option_type and option_type != direction:
            return False

        if option_type not in {"CALL", "PUT"}:
            return False

        if dte <= 0:
            return False

        if dte < min_dte or dte > max_dte:
            return False

        if price > max_premium:
            return False

        if option_type == "CALL":
            if delta <= 0:
                return False
        elif option_type == "PUT":
            if delta >= 0:
                return False

        return True

    # =========================
    # PROBABILITY
    # =========================
    def _estimate_probability(
        self,
        *,
        option: Dict[str, Any],
        score: float,
        tier: str,
        direction: Optional[str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        option_type = self._normalize_direction(option.get("option_type")) or direction or "CALL"

        result = self.probability_engine.evaluate_trade_probability(
            ai_score=safe(context.get("ai_score", score)),
            confluence=safe(context.get("confluence", score)),
            pressure=safe(context.get("pressure", score)),
            momentum=safe(context.get("momentum", score)),
            elasticity=safe(context.get("elasticity", score)),
            regime_confidence=safe(context.get("regime_confidence", score)),
            liquidity_sweep=safe(context.get("liquidity_sweep", 0.50)),
            tier_history=safe(context.get("tier_history", self._tier_history_score(tier))),
            symbol=safe_str(option.get("symbol")),
            side=option_type,
        )
        return result

    # =========================
    # SCORING
    # =========================
    def _score_option(
        self,
        *,
        o: Dict[str, Any],
        underlying_price: float,
        signal_score: float,
        tier: str,
        direction: Optional[str],
    ) -> float:

        strike = safe(o.get("strike"))
        premium = safe(o.get("price"))
        dte = safe_int(o.get("days_to_expiry"))
        delta = safe(o.get("delta"))
        option_type = self._normalize_direction(o.get("option_type"))
        moneyness = safe_str(o.get("moneyness")).upper()
        win_probability = safe(o.get("win_probability"))

        if underlying_price <= 0:
            return 0.0

        distance = abs(strike - underlying_price) / underlying_price

        if tier == "ELITE":
            atm_penalty = distance * 1.8
        elif tier == "QUALIFIED":
            atm_penalty = distance * 2.8
        else:
            atm_penalty = distance * 4.5

        premium_penalty = premium * 0.015
        dte_penalty = abs(dte - 14) * 0.05

        target_delta = self._delta_target_for_tier(tier)
        delta_gap = abs(abs(delta) - target_delta)
        delta_penalty = delta_gap * 1.5

        strike_fit_bonus = self._directional_strike_fit_bonus(
            option_type=option_type,
            strike=strike,
            spot=underlying_price,
            direction=direction,
        )

        moneyness_bonus = self._moneyness_bonus(moneyness, tier)
        signal_boost = float(signal_score)
        probability_boost = win_probability * 1.25

        score = (
            signal_boost
            + probability_boost
            + strike_fit_bonus
            + moneyness_bonus
            - atm_penalty
            - premium_penalty
            - dte_penalty
            - delta_penalty
        )

        return score

    # =========================
    # PACKAGING
    # =========================
    def _build_selection_payload(
        self,
        *,
        option: Dict[str, Any],
        underlying_price: float,
        signal_score: float,
        tier: str,
        direction: Optional[str],
        rank_score: float,
    ) -> Dict[str, Any]:
        out = dict(option)

        option_type = self._normalize_direction(out.get("option_type"))
        resolved_direction = direction or option_type or "CALL"

        out["selected"] = True
        out["selection_engine"] = "OptionsIntelligenceEngine"
        out["selection_tier"] = tier
        out["selection_direction"] = resolved_direction
        out["selection_rank_score"] = round(rank_score, 6)
        out["underlying_price"] = safe(out.get("underlying_price"), underlying_price)
        out["signal_score"] = float(signal_score)
        out["contract_type"] = option_type
        out["premium"] = safe(out.get("price"))
        out["days_to_expiry"] = safe_int(out.get("days_to_expiry"))
        out["execution_ready"] = False
        out["tradable"] = bool(out.get("tradable", False))
        out["intent"] = f"BUY_{resolved_direction}"

        out["win_probability"] = round(safe(out.get("win_probability")), 6)
        out["loss_probability"] = round(safe(out.get("loss_probability")), 6)
        out["confidence_label"] = safe_str(out.get("confidence_label"), "LOW")
        out["expected_edge"] = safe_str(out.get("expected_edge"), "WEAK")
        out["approve_trade"] = bool(out.get("approve_trade", False))

        return out

    # =========================
    # HELPERS
    # =========================
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

    def _delta_target_for_tier(self, tier: str) -> float:
        return float(self.tier_delta_targets.get(tier, self.tier_delta_targets["DEFAULT"]))

    def _tier_history_score(self, tier: str) -> float:
        if tier == "ELITE":
            return 0.80
        if tier == "QUALIFIED":
            return 0.68
        if tier == "WATCH":
            return 0.55
        return 0.50

    def _directional_strike_fit_bonus(
        self,
        *,
        option_type: str,
        strike: float,
        spot: float,
        direction: Optional[str],
    ) -> float:
        if spot <= 0:
            return 0.0

        if direction and option_type != direction:
            return -5.0

        distance = abs(strike - spot) / spot
        bonus = max(0.0, 0.35 - distance)

        if option_type == "CALL":
            if strike <= spot * 1.02:
                bonus += 0.10
        elif option_type == "PUT":
            if strike >= spot * 0.98:
                bonus += 0.10

        return bonus

    def _moneyness_bonus(self, moneyness: str, tier: str) -> float:
        m = moneyness.upper()

        if tier == "ELITE":
            if m == "ATM":
                return 0.35
            if m == "ITM":
                return 0.20
            return 0.05

        if tier == "QUALIFIED":
            if m == "ATM":
                return 0.25
            if m == "ITM":
                return 0.15
            return 0.03

        if m == "ATM":
            return 0.15
        if m == "ITM":
            return 0.08
        return 0.01