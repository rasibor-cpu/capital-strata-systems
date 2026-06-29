"""
Performance Optimizer for CSS Trading Optimization Framework
"""

from typing import Dict, Any, List

class PerformanceOptimizer:
    """
    Evaluates historical performance gaps.
    """
    @staticmethod
    def analyze_performance_gaps(asset_perf: Dict[str, Any]) -> List[str]:
        """Produce recommendations to reduce allocations for loss-making asset classes."""
        recommendations = []
        for aclass, stats in asset_perf.items():
            total_pnl = stats.get("total_pnl", 0.0)
            if total_pnl < 0:
                recommendations.append(
                    f"Reduce exposure cap for underperforming asset class {aclass} (PnL: {total_pnl:.2f})."
                )
        return recommendations
