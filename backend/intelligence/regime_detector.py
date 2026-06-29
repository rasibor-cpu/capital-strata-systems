"""
Market Regime Detector for CSS Trading Intelligence Foundation
"""

from typing import List, Any

class RegimeDetector:
    """
    Evaluates recent event streams to classify the active market regime.
    """
    @staticmethod
    def detect_regime(recent_events: List[Any], avg_latency: float) -> str:
        """Classify regime based on warning frequencies, approvals, and latency metrics."""
        warning_events = [e for e in recent_events if e.severity in ("WARNING", "CRITICAL")]
        
        if len(warning_events) >= 5 or avg_latency > 500.0:
            return "HIGH_VOLATILITY"
            
        approvals = len([e for e in recent_events if e.event_type == "TRADE_APPROVED"])
        rejections = len([e for e in recent_events if e.event_type == "TRADE_REJECTED"])
        
        if approvals > rejections:
            return "BULLISH"
        elif rejections > approvals:
            return "BEARISH"
            
        return "RANGE_BOUND"
