from __future__ import annotations

from typing import Any, Mapping


class TradeOutcomeAttributionError(ValueError):
    """Exception raised when trade outcome attribution encounters invalid input or configurations."""
    pass


class TradeOutcomeAttributionEngine:
    """
    Advisory-only Trade Outcome Attribution Engine.
    Explains completed trade outcomes by attributing realized PnL across multiple factors.
    Runs strictly in shadow mode with zero runtime impact.
    """

    def __init__(self) -> None:
        pass

    def attribute_outcome(
        self,
        completed_trade: Mapping[str, Any],
        quality_output: Mapping[str, Any] | None = None,
        explanation_output: Mapping[str, Any] | None = None,
        execution_output: Mapping[str, Any] | None = None,
        realized_pnl: float | None = None,
        market_regime: str | None = None,
        execution_metrics: Mapping[str, Any] | None = None,
        risk_metrics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Attributes a completed trade outcome across trade quality, execution quality, regime, and risk.
        Fails closed by raising TradeOutcomeAttributionError if inputs are malformed or missing key metrics.
        """
        # Validate completed_trade is mapping
        if not isinstance(completed_trade, Mapping):
            raise TradeOutcomeAttributionError("completed_trade must be a Mapping")

        # Validate required trade identifiers
        for field in ["trade_id", "symbol", "asset_class"]:
            val = completed_trade.get(field)
            if not val or not isinstance(val, str) or not val.strip():
                raise TradeOutcomeAttributionError(f"Missing or empty required field in completed_trade: {field}")

        symbol = completed_trade["symbol"].strip().upper()

        # Parse Realized PnL (required)
        pnl = realized_pnl
        if pnl is None:
            pnl_val = completed_trade.get("realized_pnl")
            if pnl_val is None:
                pnl_val = completed_trade.get("pnl")
            if pnl_val is not None:
                try:
                    pnl = float(pnl_val)
                except (ValueError, TypeError) as exc:
                    raise TradeOutcomeAttributionError("Realized PnL must be numeric") from exc

        if pnl is None:
            raise TradeOutcomeAttributionError("Realized PnL is required for outcome attribution")

        is_win = pnl > 0.0

        # Handle optional contexts safely
        q_out = quality_output if quality_output is not None else {}
        exp_out = explanation_output if explanation_output is not None else {}
        exec_out = execution_output if execution_output is not None else {}
        exec_met = execution_metrics if execution_metrics is not None else {}
        risk_met = risk_metrics if risk_metrics is not None else {}

        # 1. Trade Quality Contribution
        trade_quality_score = q_out.get("trade_quality_score") or exp_out.get("explanation_score")
        if trade_quality_score is not None:
            try:
                tq_score = float(trade_quality_score)
                trade_quality_contribution = round(max(-100.0, min(100.0, (tq_score - 60.0) * 2.5)), 4)
            except (ValueError, TypeError):
                trade_quality_contribution = 0.0
        else:
            trade_quality_contribution = 0.0

        # 2. Execution Contribution
        execution_quality_score = exec_out.get("execution_quality_score")
        if execution_quality_score is not None:
            try:
                ex_score = float(execution_quality_score)
                execution_contribution = round(max(-100.0, min(100.0, (ex_score - 60.0) * 2.5)), 4)
            except (ValueError, TypeError):
                execution_contribution = 0.0
        else:
            execution_contribution = 0.0

        # 3. Regime Contribution
        regime_contribution = 0.0
        if exp_out and "Regime Mismatch Detected" in exp_out.get("opposing_factors", []):
            regime_contribution = -50.0
        else:
            cand_regime = completed_trade.get("market_regime") or completed_trade.get("regime")
            mkt_regime = market_regime or reg_ctx_val if (reg_ctx_val := exp_out.get("regime_notes")) else None
            # Extract regime names
            if cand_regime is not None:
                cand_str = str(cand_regime).strip().upper()
                if market_regime is not None:
                    mkt_str = str(market_regime).strip().upper()
                    if cand_str == mkt_str:
                        regime_contribution = 50.0
                    else:
                        regime_contribution = -50.0

        # 4. Risk Contribution
        risk_contribution = 30.0  # Default neutral/acceptable
        if exp_out:
            opp_factors = exp_out.get("opposing_factors", [])
            if "High Portfolio Risk Level" in opp_factors or "High Concentration Risk" in opp_factors:
                risk_contribution = -40.0
        elif risk_met:
            risk_level = str(risk_met.get("risk_level", "")).strip().upper()
            if risk_level == "HIGH":
                risk_contribution = -40.0
            else:
                concen = risk_met.get("concentration_risk") or risk_met.get("concentration")
                if concen is not None:
                    try:
                        c_val = float(concen)
                        if c_val > 0.5 or c_val > 50.0:
                            risk_contribution = -40.0
                    except (ValueError, TypeError):
                        pass

        # 5. Timing Contribution (based on slippage and latency)
        timing_contribution = 0.0
        latency_ms = exec_out.get("latency_ms") or exec_met.get("latency_ms")
        if latency_ms is None:
            order_latency = exec_met.get("order_latency") or exec_met.get("latency")
            if order_latency is not None:
                try:
                    latency_ms = float(order_latency) * 1000.0
                except (ValueError, TypeError):
                    pass

        slippage_bps = exec_out.get("slippage_bps") or exec_met.get("slippage_bps")
        if slippage_bps is None:
            if "expected_entry_price" in exec_met and "actual_fill_price" in exec_met:
                try:
                    exp_pr = float(exec_met["expected_entry_price"])
                    act_pr = float(exec_met["actual_fill_price"])
                    if exp_pr > 0.0:
                        slippage_bps = abs(act_pr - exp_pr) / exp_pr * 10000.0
                except (ValueError, TypeError):
                    pass

        if latency_ms is not None:
            try:
                lat = float(latency_ms)
                if lat > 500.0:
                    timing_contribution -= 30.0
                elif lat < 50.0:
                    timing_contribution += 20.0
            except (ValueError, TypeError):
                pass

        if slippage_bps is not None:
            try:
                slip = float(slippage_bps)
                if slip > 20.0:
                    timing_contribution -= 30.0
                elif slip == 0.0:
                    timing_contribution += 20.0
            except (ValueError, TypeError):
                pass

        timing_contribution = round(max(-100.0, min(100.0, timing_contribution)), 4)

        # 6. Overall Attribution Score & Confidence
        # Evaluate how well trade quality predictions matched outcome
        pred_score = 70.0
        if trade_quality_score is not None:
            try:
                pred_score = float(trade_quality_score)
            except (ValueError, TypeError):
                pass

        if is_win:
            overall_attribution_score = round(max(0.0, min(100.0, pred_score)), 4)
        else:
            overall_attribution_score = round(max(0.0, min(100.0, 100.0 - pred_score)), 4)

        # Confidence Calculation
        confidence = 0.5
        if quality_output:
            confidence += 0.15
        if explanation_output:
            confidence += 0.15
        if execution_output:
            confidence += 0.15
        if market_regime:
            confidence += 0.05
        if execution_metrics:
            confidence += 0.05
        if risk_metrics:
            confidence += 0.05
        confidence = round(max(0.0, min(1.0, confidence)), 4)

        # Determine Primary Success & Failure Factors & Lessons Learned
        primary_success_factors: list[str] = []
        primary_failure_factors: list[str] = []
        lessons_learned: list[str] = []

        if is_win:
            if trade_quality_contribution >= 40.0:
                primary_success_factors.append("Optimal Trade Quality")
            if execution_contribution >= 40.0:
                primary_success_factors.append("Excellent Execution Quality")
            if regime_contribution >= 40.0:
                primary_success_factors.append("Favorable Market Regime Alignment")
            if timing_contribution >= 20.0:
                primary_success_factors.append("Efficient Execution Timing")

            # Default fallback for win
            if not primary_success_factors:
                primary_success_factors.append("Acceptable execution and metrics alignment")
            lessons_learned.append("Maintain strategy parameters for currently aligned regime.")
        else:
            if trade_quality_contribution < 0.0:
                primary_failure_factors.append("Poor Trade Quality")
                lessons_learned.append("Enforce Unified Trade Gate filters to block low-quality candidates.")
            if execution_contribution < 0.0:
                primary_failure_factors.append("Poor Execution Quality")
            if regime_contribution < 0.0:
                primary_failure_factors.append("Market Regime Mismatch")
                lessons_learned.append("Recalibrate regime gates to prevent execution in mismatched environments.")
            if risk_contribution < 0.0:
                primary_failure_factors.append("Elevated Risk Parameters")
                lessons_learned.append("Adjust concentration limit thresholds.")
            if timing_contribution < 0.0:
                primary_failure_factors.append("Inefficient Execution Timing / Latency")
                lessons_learned.append("Optimize broker connectivity or execution route to reduce latency and slippage.")

            # Default fallback for loss
            if not primary_failure_factors:
                primary_failure_factors.append("Market-driven adverse price movement")
                lessons_learned.append("Review market micro-structure logs for event-driven volatility.")

        # Construct Summary
        status_str = "WINNING" if is_win else "LOSING"
        pnl_sign = "+" if pnl > 0 else ""
        attribution_summary = (
            f"Advisory Attribution: Completed {status_str} trade for {symbol} (realized PnL {pnl_sign}{pnl:.2f}). "
            f"Attribution score: {overall_attribution_score:.1f}% accuracy based on system inputs. "
        )
        if is_win:
            attribution_summary += f"Primary success drivers: {', '.join(primary_success_factors)}."
        else:
            attribution_summary += f"Primary failure contributors: {', '.join(primary_failure_factors)}."

        return {
            "attribution_summary": attribution_summary,
            "primary_success_factors": primary_success_factors,
            "primary_failure_factors": primary_failure_factors,
            "execution_contribution": execution_contribution,
            "trade_quality_contribution": trade_quality_contribution,
            "regime_contribution": regime_contribution,
            "risk_contribution": risk_contribution,
            "timing_contribution": timing_contribution,
            "overall_attribution_score": overall_attribution_score,
            "confidence": confidence,
            "lessons_learned": lessons_learned,
            "advisory_only": True,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
        }
