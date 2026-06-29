"""
Parameter Optimizer for CSS Trading Optimization Framework
"""

from typing import Dict, Any

class ParameterOptimizer:
    """
    Analyzes win-loss statistics to recommend optimal parameters.
    """
    @staticmethod
    def optimize_parameters(win_loss_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest leverage and risk multipliers mapped to recent win rates."""
        win_rate = win_loss_stats.get("win_rate", 0.5)
        
        if win_rate > 0.6:
            leverage = 3.0
            risk_mult = 1.2
        elif win_rate < 0.4:
            leverage = 1.0
            risk_mult = 0.7
        else:
            leverage = 2.0
            risk_mult = 1.0
            
        return {
            "recommended_leverage": leverage,
            "recommended_risk_multiplier": risk_mult,
            "reason": f"Adjusted parameters for {win_rate*100:.1f}% win rate."
        }
