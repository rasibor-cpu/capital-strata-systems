from __future__ import annotations

from typing import Any, Mapping


class ExplainableDecisionEngineError(ValueError):
    """Exception raised when explainable decision engine encounters invalid input or configurations."""
    pass


class ExplainableDecisionEngine:
    """
    Advisory-only Explainable Decision Engine.
    Produces structured, auditable explanations for eligible trade decisions.
    Runs strictly in shadow mode with zero runtime impact.
    """

    def __init__(self) -> None:
        pass

    def explain_decision(
        self,
        candidate: Mapping[str, Any],
        quality_output: Mapping[str, Any] | None = None,
        signal_context: Mapping[str, Any] | None = None,
        risk_context: Mapping[str, Any] | None = None,
        regime_context: Mapping[str, Any] | None = None,
        market_metrics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generates a structured, deterministic explanation for a trade decision candidate.
        Fails closed by raising ExplainableDecisionEngineError if candidate inputs are malformed or missing key identifiers.
        """
        # Validate inputs
        if not isinstance(candidate, Mapping):
            raise ExplainableDecisionEngineError("candidate must be a Mapping")

        # Validate required trade identifiers
        for field in ["trade_id", "symbol", "asset_class"]:
            val = candidate.get(field)
            if not val or not isinstance(val, str) or not val.strip():
                raise ExplainableDecisionEngineError(f"Missing or empty required field in candidate: {field}")

        symbol = candidate["symbol"].strip().upper()

        # Handle optional contexts safely by using empty dicts for easier querying
        q_out = quality_output if quality_output is not None else {}
        sig_ctx = signal_context if signal_context is not None else {}
        risk_ctx = risk_context if risk_context is not None else {}
        reg_ctx = regime_context if regime_context is not None else {}
        mkt_met = market_metrics if market_metrics is not None else {}

        # 1. Determine explanation score and quality grade
        explanation_score, quality_grade = self._determine_score_and_grade(
            candidate, q_out, sig_ctx, risk_ctx, reg_ctx, mkt_met
        )

        # 2. Analyze Factors
        supporting_factors: list[str] = []
        opposing_factors: list[str] = []
        confidence_drivers: list[str] = []
        confidence_detractors: list[str] = []

        # Trade Quality Factors (from Phase 47A)
        if q_out:
            for strength in q_out.get("strengths", []):
                supporting_factors.append(strength)
                confidence_drivers.append(strength)
            for weakness in q_out.get("weaknesses", []):
                opposing_factors.append(weakness)
                confidence_detractors.append(weakness)

            q_score = q_out.get("trade_quality_score", 0.0)
            if q_score >= 80.0:
                supporting_factors.append("High Trade Quality Assessment")
                confidence_drivers.append("High Trade Quality Assessment")
            elif q_score < 60.0:
                opposing_factors.append("Low Trade Quality Assessment")
                confidence_detractors.append("Low Trade Quality Assessment")

        # Signal Context Factors
        if sig_ctx:
            sig_strength = self._get_numeric_metric(sig_ctx, ["signal_strength", "strength", "confidence", "signal_score"])
            if sig_strength is not None:
                if sig_strength >= 0.8 or sig_strength >= 80.0:
                    supporting_factors.append("Strong Signal Strength Confirmation")
                    confidence_drivers.append("Strong Signal Strength Confirmation")
                elif sig_strength < 0.5 or sig_strength < 50.0:
                    opposing_factors.append("Weak Signal Strength")
                    confidence_detractors.append("Weak Signal Strength")

        # Risk Context Factors & Notes
        risk_notes = "Risk context unavailable: no risk evaluation performed."
        if risk_ctx:
            risk_warnings: list[str] = []
            risk_level = str(risk_ctx.get("risk_level", "")).strip().upper()
            if risk_level == "HIGH":
                opposing_factors.append("High Portfolio Risk Level")
                confidence_detractors.append("High Portfolio Risk Level")
                risk_warnings.append("Risk level is marked as HIGH.")

            concen_risk = self._get_numeric_metric(risk_ctx, ["concentration_risk", "concentration"])
            if concen_risk is not None and (concen_risk > 0.5 or concen_risk > 50.0):
                opposing_factors.append("High Concentration Risk")
                confidence_detractors.append("High Concentration Risk")
                risk_warnings.append(f"Concentration risk is elevated: {concen_risk}.")

            port_risk = self._get_numeric_metric(risk_ctx, ["portfolio_risk", "risk_score"])
            if port_risk is not None and (port_risk > 0.4 or port_risk > 40.0):
                opposing_factors.append("Elevated Portfolio Risk Score")
                confidence_detractors.append("Elevated Portfolio Risk Score")
                risk_warnings.append(f"Portfolio risk score is high: {port_risk}.")

            if risk_warnings:
                risk_notes = f"Risk warnings identified: {' '.join(risk_warnings)}"
            else:
                supporting_factors.append("Acceptable Risk Levels")
                confidence_drivers.append("Acceptable Risk Levels")
                risk_notes = "Risk levels are within normal bounds and limits."

        # Regime Context Factors & Notes
        regime_notes = "Regime context unavailable: no regime alignment verification performed."
        # Attempt to find candidate regime
        cand_regime = candidate.get("market_regime") or candidate.get("regime")
        # Attempt to find current market regime
        mkt_regime = (
            reg_ctx.get("current_regime")
            or reg_ctx.get("market_regime")
            or reg_ctx.get("regime")
            or mkt_met.get("current_regime")
            or mkt_met.get("market_regime")
        )

        if cand_regime is not None and mkt_regime is not None:
            cand_str = str(cand_regime).strip().upper()
            mkt_str = str(mkt_regime).strip().upper()
            if cand_str and mkt_str:
                if cand_str == mkt_str:
                    supporting_factors.append("Aligned Market Regime")
                    confidence_drivers.append("Aligned Market Regime")
                    regime_notes = f"Market regime matches candidate expectations ({cand_str})."
                else:
                    opposing_factors.append("Regime Mismatch Detected")
                    confidence_detractors.append("Regime Mismatch Detected")
                    regime_notes = f"Regime mismatch: candidate expects {cand_str} but current regime is {mkt_str}."

        # Market Metrics Factors & Notes
        market_notes = "Market metrics unavailable: no market condition checks performed."
        if mkt_met:
            market_warnings: list[str] = []
            
            # Liquidity
            liq_val = mkt_met.get("liquidity_quality") or mkt_met.get("liquidity_rating") or mkt_met.get("liquidity")
            if isinstance(liq_val, str) and liq_val.strip().upper() == "LOW":
                opposing_factors.append("Low Liquidity Quality")
                confidence_detractors.append("Low Liquidity Quality")
                market_warnings.append("Market liquidity rating is LOW.")
            else:
                num_liq = self._get_numeric_metric(mkt_met, ["liquidity_score", "liquidity"])
                if num_liq is not None and (num_liq < 0.4 or num_liq < 40.0):
                    opposing_factors.append("Low Liquidity Quality")
                    confidence_detractors.append("Low Liquidity Quality")
                    market_warnings.append(f"Market liquidity score is low: {num_liq}.")

            # Spread
            spread = self._get_numeric_metric(mkt_met, ["spread", "bid_ask_spread", "spread_bps"])
            if spread is not None:
                is_bps = "spread_bps" in mkt_met
                max_spread = float(mkt_met.get("max_acceptable_spread_bps" if is_bps else "max_acceptable_spread", 50.0 if is_bps else 0.005))
                if spread >= max_spread:
                    opposing_factors.append("Wide Bid-Ask Spread")
                    confidence_detractors.append("Wide Bid-Ask Spread")
                    market_warnings.append(f"Spread {spread} exceeds or matches maximum threshold of {max_spread}.")

            # Volatility
            vol_suit = mkt_met.get("volatility_suitability")
            if vol_suit is None:
                vol_suit = mkt_met.get("volatility_suitable")
            if isinstance(vol_suit, bool) and not vol_suit:
                opposing_factors.append("Unsuitable Volatility Environment")
                confidence_detractors.append("Unsuitable Volatility Environment")
                market_warnings.append("Volatility is marked as unsuitable for candidate strategy.")
            else:
                num_vol_suit = self._get_numeric_metric(mkt_met, ["volatility_suitability", "volatility_score"])
                if num_vol_suit is not None and (num_vol_suit < 0.4 or num_vol_suit < 40.0):
                    opposing_factors.append("Unsuitable Volatility Environment")
                    confidence_detractors.append("Unsuitable Volatility Environment")
                    market_warnings.append(f"Volatility suitability score is low: {num_vol_suit}.")

            if market_warnings:
                market_notes = f"Market warnings: {' '.join(market_warnings)}"
            else:
                supporting_factors.append("Optimal Market Conditions")
                confidence_drivers.append("Optimal Market Conditions")
                market_notes = "Market conditions (liquidity, spread, volatility) are highly favorable."

        # Unique lists to maintain clean explanation
        supporting_factors = sorted(list(set(supporting_factors)))
        opposing_factors = sorted(list(set(opposing_factors)))
        confidence_drivers = sorted(list(set(confidence_drivers)))
        confidence_detractors = sorted(list(set(confidence_detractors)))

        # 3. Decision Summary formulation
        if opposing_factors:
            decision_summary = (
                f"Advisory Explanation: Trade candidate {symbol} was evaluated with a score of {explanation_score:.1f} "
                f"({quality_grade}). Warnings or detractors were identified regarding: {', '.join(opposing_factors)}."
            )
        else:
            decision_summary = (
                f"Advisory Explanation: Trade candidate {symbol} was evaluated with a score of {explanation_score:.1f} "
                f"({quality_grade}). The trade decision is fully supported by the available metrics and contexts."
            )

        return {
            "decision_summary": decision_summary,
            "explanation_score": explanation_score,
            "quality_grade": quality_grade,
            "supporting_factors": supporting_factors,
            "opposing_factors": opposing_factors,
            "risk_notes": risk_notes,
            "regime_notes": regime_notes,
            "market_notes": market_notes,
            "confidence_drivers": confidence_drivers,
            "confidence_detractors": confidence_detractors,
            "advisory_only": True,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
        }

    def _determine_score_and_grade(
        self,
        candidate: Mapping[str, Any],
        q_out: Mapping[str, Any],
        sig_ctx: Mapping[str, Any],
        risk_ctx: Mapping[str, Any],
        reg_ctx: Mapping[str, Any],
        mkt_met: Mapping[str, Any],
    ) -> tuple[float, str]:
        # If quality_output is provided, use its score as the base
        if q_out and "trade_quality_score" in q_out:
            try:
                score = float(q_out["trade_quality_score"])
                return round(max(0.0, min(100.0, score)), 4), self._get_grade(score)
            except (ValueError, TypeError):
                pass

        # Otherwise calculate explanation score
        score = 70.0  # Base neutral score

        # 1. Signal Context Adjustment
        sig_strength = self._get_numeric_metric(sig_ctx, ["signal_strength", "strength", "confidence", "signal_score"])
        if sig_strength is not None:
            normalized_sig = sig_strength / 100.0 if sig_strength > 1.0 else sig_strength
            # Add up to 30 points
            score += (normalized_sig - 0.5) * 60.0

        # 2. Risk Context Adjustment
        risk_level = str(risk_ctx.get("risk_level", "")).strip().upper()
        if risk_level == "HIGH":
            score -= 30.0
        elif risk_level == "LOW":
            score += 10.0

        concen_risk = self._get_numeric_metric(risk_ctx, ["concentration_risk", "concentration"])
        if concen_risk is not None:
            normalized_concen = concen_risk / 100.0 if concen_risk > 1.0 else concen_risk
            if normalized_concen > 0.5:
                score -= (normalized_concen - 0.5) * 40.0

        # 3. Regime Mismatch Adjustment
        cand_regime = candidate.get("market_regime") or candidate.get("regime")
        mkt_regime = (
            reg_ctx.get("current_regime")
            or reg_ctx.get("market_regime")
            or reg_ctx.get("regime")
            or mkt_met.get("current_regime")
            or mkt_met.get("market_regime")
        )
        if cand_regime is not None and mkt_regime is not None:
            if str(cand_regime).strip().upper() != str(mkt_regime).strip().upper():
                score -= 30.0
            else:
                score += 10.0

        # 4. Market Metrics Adjustment
        liq_val = mkt_met.get("liquidity_quality") or mkt_met.get("liquidity_rating") or mkt_met.get("liquidity")
        if isinstance(liq_val, str) and liq_val.strip().upper() == "LOW":
            score -= 20.0
        else:
            num_liq = self._get_numeric_metric(mkt_met, ["liquidity_score", "liquidity"])
            if num_liq is not None:
                normalized_liq = num_liq / 100.0 if num_liq > 1.0 else num_liq
                if normalized_liq < 0.4:
                    score -= (0.4 - normalized_liq) * 50.0

        spread = self._get_numeric_metric(mkt_met, ["spread", "bid_ask_spread", "spread_bps"])
        if spread is not None:
            is_bps = "spread_bps" in mkt_met
            max_spread = float(mkt_met.get("max_acceptable_spread_bps" if is_bps else "max_acceptable_spread", 50.0 if is_bps else 0.005))
            if spread >= max_spread:
                score -= 20.0

        vol_suit = mkt_met.get("volatility_suitability")
        if vol_suit is None:
            vol_suit = mkt_met.get("volatility_suitable")
        if isinstance(vol_suit, bool) and not vol_suit:
            score -= 20.0

        final_score = round(max(0.0, min(100.0, score)), 4)
        return final_score, self._get_grade(final_score)

    @staticmethod
    def _get_numeric_metric(ctx: Mapping[str, Any], fields: list[str]) -> float | None:
        for field in fields:
            if field in ctx:
                val = ctx[field]
                if val is None:
                    continue
                if isinstance(val, bool):
                    continue
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
        return None

    @staticmethod
    def _get_grade(score: float) -> str:
        if score >= 90.0:
            return "A"
        elif score >= 80.0:
            return "B"
        elif score >= 70.0:
            return "C"
        elif score >= 60.0:
            return "D"
        else:
            return "F"
