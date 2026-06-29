"""
Intelligence Service Coordinator for CSS Trading Intelligence Foundation
"""

from typing import Dict, Any, List
from backend.events.visibility_layer import EventVisibilityLayer
from backend.metrics.metrics_service import MetricsService
from backend.intelligence.strategy_analytics import StrategyAnalytics
from backend.intelligence.performance_analyzer import PerformanceAnalyzer
from backend.intelligence.portfolio_analyzer import PortfolioAnalyzer
from backend.intelligence.regime_detector import RegimeDetector
from backend.intelligence.confidence_engine import ConfidenceEngine
from backend.intelligence.recommendation_engine import RecommendationEngine
from backend.intelligence.explainability import Explainability

class IntelligenceService:
    """
    Main Service for Trading Intelligence.
    Acts as the entrypoint facade for all passive analytics engines.
    """
    def __init__(self, visibility_layer: EventVisibilityLayer, metrics_service: MetricsService):
        self.visibility_layer = visibility_layer
        self.metrics_service = metrics_service
        self.strategy_analytics = StrategyAnalytics()
        self.performance_analyzer = PerformanceAnalyzer()
        self.portfolio_analyzer = PortfolioAnalyzer()
        self.regime_detector = RegimeDetector()
        self.confidence_engine = ConfidenceEngine()
        self.recommendation_engine = RecommendationEngine()
        self.explainability = Explainability()

    def get_portfolio_state(self) -> Dict[str, float]:
        """Summarise current asset allocations dynamically from past approvals."""
        recent = self.visibility_layer.get_recent_events(limit=50)
        state = {"EQUITIES": 0.0, "FX": 0.0, "CRYPTO": 0.0, "OPTIONS": 0.0, "FUTURES": 0.0}
        for e in recent:
            if e.event_type == "TRADE_APPROVED":
                ac = str(e.payload.get("asset_class", "EQUITIES")).upper()
                qty = float(e.payload.get("quantity", 0.0) or 0.0)
                price = float(e.payload.get("entry_price", 1.0) or 1.0)
                state[ac] = state.get(ac, 0.0) + (qty * price)
        return state

    def get_trades_list(self) -> List[Dict[str, Any]]:
        """Fetch trading outcomes from approved events."""
        recent = self.visibility_layer.get_recent_events(limit=100)
        trades = []
        for e in recent:
            if e.event_type == "TRADE_APPROVED":
                trades.append({
                    "trade_id": e.payload.get("trade_id"),
                    "asset_class": e.payload.get("asset_class", "EQUITIES"),
                    "symbol": e.payload.get("symbol", "UNKNOWN"),
                    "realized_pnl": e.payload.get("realized_pnl", 10.0),
                    "side": "BUY"
                })
        return trades

    def get_trading_intelligence_report(self) -> Dict[str, Any]:
        """Aggregate all advisory and regime classification details into one report."""
        trades = self.get_trades_list()
        portfolio_state = self.get_portfolio_state()
        recent_events = self.visibility_layer.get_recent_events(limit=20)
        telemetry_snap = self.metrics_service.telemetry.compile_telemetry(0)
        avg_latency = telemetry_snap.get("publish_latency_avg_ms", 0.0)
        
        regime = self.regime_detector.detect_regime(recent_events, avg_latency)
        win_loss = self.strategy_analytics.calculate_win_loss(trades)
        drawdown = self.strategy_analytics.calculate_drawdown_trend(trades)
        asset_perf = self.performance_analyzer.calculate_asset_class_performance(trades)
        concentration = self.portfolio_analyzer.calculate_concentration(portfolio_state)
        
        recs = self.recommendation_engine.generate_recommendations(concentration, win_loss)
        
        default_candidate = {"symbol": "SPY", "probability": 0.7}
        confidence = self.confidence_engine.calculate_confidence(default_candidate, regime)
        
        return {
            "market_regime": regime,
            "win_loss_statistics": win_loss,
            "drawdown_trends": drawdown,
            "asset_class_performance": asset_perf,
            "portfolio_concentration": concentration,
            "recommendations": recs,
            "advisory_confidence_score": confidence
        }
