# =========================================================
# FILE: backend/intelligence/probability_prediction_engine.py
# Capital Strata Systems (CSS)
# Pre-Trade Win Probability Engine
# Non-Regressive Additive Module
# =========================================================

from __future__ import annotations

from typing import Dict, Any


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


class ProbabilityPredictionEngine:
    """
    CSS Golden Bullet Layer:
    Predicts likelihood that a trade will end positive BEFORE entry.

    This module is additive only.
    It does not alter existing engines.
    It only computes probability scores for orchestrator use.
    """

    def __init__(self):
        self.minimum_probability_floor = 0.50
        self.high_confidence_threshold = 0.75
        self.medium_confidence_threshold = 0.62

    # =====================================================
    # MAIN ENTRY
    # =====================================================
    def evaluate_trade_probability(
        self,
        *,
        ai_score: float,
        confluence: float,
        pressure: float,
        momentum: float,
        elasticity: float,
        regime_confidence: float,
        liquidity_sweep: float,
        tier_history: float,
        symbol: str = "",
        side: str = ""
    ) -> Dict[str, Any]:
        """
        Returns:
            {
                win_probability,
                loss_probability,
                confidence_label,
                expected_edge,
                approve_trade
            }
        """

        ai_score = _safe(ai_score)
        confluence = _safe(confluence)
        pressure = _safe(pressure)
        momentum = _safe(momentum)
        elasticity = _safe(elasticity)
        regime_confidence = _safe(regime_confidence)
        liquidity_sweep = _safe(liquidity_sweep)
        tier_history = _safe(tier_history)

        # -------------------------------------------------
        # Weighted Fusion Model
        # -------------------------------------------------
        win_probability = (
            ai_score * 0.20 +
            confluence * 0.15 +
            pressure * 0.15 +
            momentum * 0.10 +
            elasticity * 0.10 +
            regime_confidence * 0.10 +
            liquidity_sweep * 0.10 +
            tier_history * 0.10
        )

        # Clamp to valid range
        win_probability = max(0.0, min(1.0, win_probability))
        loss_probability = 1.0 - win_probability

        # -------------------------------------------------
        # Confidence Labels
        # -------------------------------------------------
        if win_probability >= self.high_confidence_threshold:
            confidence_label = "HIGH"
            expected_edge = "STRONG"
        elif win_probability >= self.medium_confidence_threshold:
            confidence_label = "MEDIUM"
            expected_edge = "MODERATE"
        else:
            confidence_label = "LOW"
            expected_edge = "WEAK"

        approve_trade = win_probability >= self.minimum_probability_floor

        return {
            "symbol": symbol,
            "side": side,
            "win_probability": round(win_probability, 4),
            "loss_probability": round(loss_probability, 4),
            "confidence_label": confidence_label,
            "expected_edge": expected_edge,
            "approve_trade": approve_trade,
        }

    # =====================================================
    # OPTIONAL DISPLAY FORMATTER
    # =====================================================
    def dashboard_line(self, result: Dict[str, Any]) -> str:
        """
        Example:
        BTC-USD | CALL | WinProb: 78.4% | LossProb: 21.6% | HIGH
        """
        symbol = result.get("symbol", "")
        side = result.get("side", "")
        wp = result.get("win_probability", 0.0) * 100
        lp = result.get("loss_probability", 0.0) * 100
        conf = result.get("confidence_label", "LOW")

        return (
            f"{symbol} | {side} | "
            f"WinProb: {wp:.1f}% | "
            f"LossProb: {lp:.1f}% | "
            f"{conf}"
        )