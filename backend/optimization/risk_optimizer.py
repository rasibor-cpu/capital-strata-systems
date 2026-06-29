"""
Risk Parameter Optimizer for CSS Trading Optimization Framework
"""

from typing import Dict, Any

class RiskOptimizer:
    """
    Formulates risk parameter scaling suggestions.
    """
    @staticmethod
    def optimize_risk_parameters(drawdown_trends: Dict[str, Any]) -> Dict[str, Any]:
        """Tighten drawdown limit when cumulative drawdown starts exceeding bounds."""
        max_dd = drawdown_trends.get("max_drawdown", 0.0)
        
        suggested_drawdown_limit = 15.0
        if max_dd > 10.0:
            suggested_drawdown_limit = 8.0
            
        return {
            "suggested_drawdown": suggested_drawdown_limit,
            "exposure_cap": 0.15 if max_dd > 10.0 else 0.25
        }
