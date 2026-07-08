import sys
import types
from typing import Any, Mapping

# 1. Define a Mock TradeQualityScoringEngine class that behaves exactly like the Phase 47A implementation
class MockTradeQualityScoringEngineError(ValueError):
    pass

class MockTradeQualityScoringEngine:
    def __init__(self) -> None:
        pass

    def score_trade(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(candidate, Mapping):
            raise MockTradeQualityScoringEngineError("candidate must be a Mapping")
        if not isinstance(market_metrics, Mapping):
            raise MockTradeQualityScoringEngineError("market_metrics must be a Mapping")

        for field in ["trade_id", "symbol", "asset_class"]:
            val = candidate.get(field)
            if not val or not isinstance(val, str) or not val.strip():
                raise MockTradeQualityScoringEngineError(f"Missing or empty required field: {field}")

        dimension_scores: dict[str, float] = {}

        # 1. Expected Edge
        dimension_scores["expected_edge"] = self._score_expected_edge(candidate, market_metrics)
        # 2. Risk/Reward Ratio
        dimension_scores["risk_reward_ratio"] = self._score_risk_reward_ratio(candidate, market_metrics)
        # 3. Signal Agreement Score
        dimension_scores["signal_agreement"] = self._score_signal_agreement(candidate, market_metrics)
        # 4. Historical Strategy Reliability
        dimension_scores["historical_reliability"] = self._score_historical_reliability(candidate, market_metrics)
        # 5. Market Regime Alignment
        dimension_scores["market_regime_alignment"] = self._score_market_regime_alignment(candidate, market_metrics)
        # 6. Liquidity Quality
        dimension_scores["liquidity_quality"] = self._score_liquidity_quality(candidate, market_metrics)
        # 7. Spread Quality
        dimension_scores["spread_quality"] = self._score_spread_quality(candidate, market_metrics)
        # 8. Volatility Suitability
        dimension_scores["volatility_suitability"] = self._score_volatility_suitability(candidate, market_metrics)

        total_score = sum(dimension_scores.values())
        trade_quality_score = round(total_score / 8.0, 4)

        # Strengths & Weaknesses
        strengths = [self._get_strength_label(k) for k, v in dimension_scores.items() if v >= 85.0]
        weaknesses = [self._get_weakness_label(k) for k, v in dimension_scores.items() if v < 60.0]

        return {
            "trade_quality_score": trade_quality_score,
            "quality_grade": self._get_grade(trade_quality_score),
            "dimension_scores": dimension_scores,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "advisory_only": True,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
        }

    def _score_expected_edge(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> float:
        edge = candidate.get("expected_edge") or market_metrics.get("expected_edge")
        if edge is None and "expected_value" in candidate and "cost" in candidate:
            edge = float(candidate["expected_value"]) - float(candidate["cost"])
        if edge is None:
            raise MockTradeQualityScoringEngineError("Expected edge could not be determined")
        edge_f = self._to_float(edge, "expected_edge")
        target = self._to_float(market_metrics.get("target_edge", 0.05), "target_edge")
        if edge_f <= 0.0:
            return 0.0
        return round(min(100.0, max(0.0, (edge_f / target) * 100.0)), 4)

    def _score_risk_reward_ratio(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> float:
        ratio = candidate.get("risk_reward") or candidate.get("risk_reward_ratio")
        if ratio is None and "expected_reward" in candidate and "expected_risk" in candidate:
            risk = float(candidate["expected_risk"])
            if risk <= 0.0:
                return 0.0
            ratio = float(candidate["expected_reward"]) / risk
        if ratio is None:
            raise MockTradeQualityScoringEngineError("Risk/reward could not be determined")
        ratio_f = self._to_float(ratio, "risk_reward")
        if ratio_f <= 0.0:
            return 0.0
        if ratio_f >= 3.0:
            return 100.0
        if ratio_f >= 2.0:
            score = 85.0 + (ratio_f - 2.0) * 15.0
        elif ratio_f >= 1.0:
            score = 50.0 + (ratio_f - 1.0) * 35.0
        elif ratio_f >= 0.5:
            score = 20.0 + (ratio_f - 0.5) * 60.0
        else:
            score = ratio_f * 40.0
        return round(score, 4)

    def _score_signal_agreement(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> float:
        val = None
        for f in ["signal_agreement", "signal_agreement_score", "confirmation_score", "agreement"]:
            if f in candidate:
                val = candidate[f]
                break
            if f in market_metrics:
                val = market_metrics[f]
                break
        if val is None:
            raise MockTradeQualityScoringEngineError("Signal agreement missing")
        val_f = self._to_float(val, "signal_agreement")
        score = val_f * 100.0 if 0.0 <= val_f <= 1.0 else val_f
        return round(min(100.0, max(0.0, score)), 4)

    def _score_historical_reliability(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> float:
        val = None
        for f in ["historical_reliability", "strategy_reliability", "historical_win_rate", "reliability", "win_rate"]:
            if f in candidate:
                val = candidate[f]
                break
            if f in market_metrics:
                val = market_metrics[f]
                break
        if val is None:
            raise MockTradeQualityScoringEngineError("Historical reliability missing")
        val_f = self._to_float(val, "historical_reliability")
        score = val_f * 100.0 if 0.0 <= val_f <= 1.0 else val_f
        return round(min(100.0, max(0.0, score)), 4)

    def _score_market_regime_alignment(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> float:
        for f in ["market_regime_alignment", "regime_alignment", "regime_match", "regime_score"]:
            if f in candidate:
                val = candidate[f]
                return round(min(100.0, max(0.0, val * 100.0 if 0.0 <= val <= 1.0 else val)), 4)
            if f in market_metrics:
                val = market_metrics[f]
                return round(min(100.0, max(0.0, val * 100.0 if 0.0 <= val <= 1.0 else val)), 4)

        cand_reg = candidate.get("market_regime")
        mkt_reg = market_metrics.get("current_regime")
        if cand_reg is None or mkt_reg is None:
            raise MockTradeQualityScoringEngineError("Market regime alignment missing")
        if str(cand_reg).strip().upper() == str(mkt_reg).strip().upper():
            return 100.0
        return 20.0

    def _score_liquidity_quality(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> float:
        val = None
        for f in ["liquidity_quality", "liquidity_score", "liquidity_rating", "liquidity"]:
            if f in candidate:
                val = candidate[f]
                break
            if f in market_metrics:
                val = market_metrics[f]
                break
        if val is None:
            raise MockTradeQualityScoringEngineError("Liquidity missing")
        if isinstance(val, str):
            rating = val.strip().upper()
            if rating == "HIGH": return 100.0
            if rating == "MEDIUM": return 70.0
            if rating == "LOW": return 30.0
            raise MockTradeQualityScoringEngineError("Invalid rating")
        val_f = self._to_float(val, "liquidity")
        score = val_f * 100.0 if 0.0 <= val_f <= 1.0 else val_f
        return round(min(100.0, max(0.0, score)), 4)

    def _score_spread_quality(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> float:
        for f in ["spread_quality", "spread_score"]:
            if f in candidate:
                val = candidate[f]
                return round(min(100.0, max(0.0, val * 100.0 if 0.0 <= val <= 1.0 else val)), 4)
            if f in market_metrics:
                val = market_metrics[f]
                return round(min(100.0, max(0.0, val * 100.0 if 0.0 <= val <= 1.0 else val)), 4)

        spread = candidate.get("spread") or market_metrics.get("spread") or candidate.get("bid_ask_spread") or market_metrics.get("bid_ask_spread")
        if spread is None:
            raise MockTradeQualityScoringEngineError("Spread missing")
        spread_f = self._to_float(spread, "spread")
        max_spread = self._to_float(market_metrics.get("max_acceptable_spread", 0.005), "max_acceptable_spread")
        score = (1.0 - spread_f / max_spread) * 100.0
        return round(min(100.0, max(0.0, score)), 4)

    def _score_volatility_suitability(self, candidate: Mapping[str, Any], market_metrics: Mapping[str, Any]) -> float:
        val = None
        for f in ["volatility_suitability", "volatility_score", "volatility_suitable"]:
            if f in candidate:
                val = candidate[f]
                break
            if f in market_metrics:
                val = market_metrics[f]
                break
        if val is None:
            raise MockTradeQualityScoringEngineError("Volatility missing")
        if isinstance(val, bool):
            return 100.0 if val else 20.0
        val_f = self._to_float(val, "volatility")
        score = val_f * 100.0 if 0.0 <= val_f <= 1.0 else val_f
        return round(min(100.0, max(0.0, score)), 4)

    def _to_float(self, val: Any, name: str) -> float:
        if val is None or isinstance(val, bool):
            raise MockTradeQualityScoringEngineError(f"Field {name} must be numeric")
        try:
            return float(val)
        except (ValueError, TypeError):
            raise MockTradeQualityScoringEngineError(f"Field {name} must be numeric")

    def _get_grade(self, score: float) -> str:
        if score >= 90.0: return "A"
        if score >= 80.0: return "B"
        if score >= 70.0: return "C"
        if score >= 60.0: return "D"
        return "F"

    def _get_strength_label(self, key: str) -> str:
        return {
            "expected_edge": "Strong Expected Edge",
            "risk_reward_ratio": "Excellent Risk/Reward Profile",
            "signal_agreement": "High Signal Agreement",
            "historical_reliability": "Strong Historical Strategy Reliability",
            "market_regime_alignment": "Excellent Market Regime Alignment",
            "liquidity_quality": "High Liquidity Quality",
            "spread_quality": "Tight Bid-Ask Spread",
            "volatility_suitability": "Suitable Volatility Environment",
        }[key]

    def _get_weakness_label(self, key: str) -> str:
        return {
            "expected_edge": "Weak Expected Edge",
            "risk_reward_ratio": "Poor Risk/Reward Profile",
            "signal_agreement": "Weak Signal Agreement",
            "historical_reliability": "Low Historical Strategy Reliability",
            "market_regime_alignment": "Poor Market Regime Alignment",
            "liquidity_quality": "Low Liquidity Quality",
            "spread_quality": "Wide Bid-Ask Spread",
            "volatility_suitability": "Unsuitable Volatility Environment",
        }[key]

# 2. Dynamically attach mock backend.trading.trade_quality_scoring_engine
import backend.trading

mock_engine = types.ModuleType("backend.trading.trade_quality_scoring_engine")
mock_engine.TradeQualityScoringEngine = MockTradeQualityScoringEngine
mock_engine.TradeQualityScoringEngineError = MockTradeQualityScoringEngineError

# Inject the sub-module into sys.modules and attach to backend.trading
sys.modules["backend.trading.trade_quality_scoring_engine"] = mock_engine
backend.trading.trade_quality_scoring_engine = mock_engine
# Make it possible to import it from backend.trading as well
setattr(backend.trading, "trade_quality_scoring_engine", mock_engine)

