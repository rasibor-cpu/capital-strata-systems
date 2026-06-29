"""
Strategy Analytics for CSS Trading Intelligence Foundation
"""

from typing import List, Dict, Any

class StrategyAnalytics:
    """
    Computes performance statistics, win-loss ratios, and drawdowns.
    """
    @staticmethod
    def calculate_win_loss(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate total trades, win rate, and profit factor."""
        total = len(trades)
        if total == 0:
            return {"total_trades": 0, "wins_count": 0, "losses_count": 0, "win_rate": 0.0, "profit_factor": 1.0}
        
        wins = [t for t in trades if float(t.get("realized_pnl", 0.0)) > 0]
        losses = [t for t in trades if float(t.get("realized_pnl", 0.0)) <= 0]
        
        total_gains = sum(float(t.get("realized_pnl", 0.0)) for t in wins)
        total_losses = abs(sum(float(t.get("realized_pnl", 0.0)) for t in losses))
        
        profit_factor = total_gains / total_losses if total_losses > 0 else 1.0
        
        return {
            "total_trades": total,
            "wins_count": len(wins),
            "losses_count": len(losses),
            "win_rate": len(wins) / total,
            "profit_factor": profit_factor
        }

    @staticmethod
    def calculate_drawdown_trend(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Trace peak cumulative PnL to determine drawdowns."""
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        
        for t in trades:
            cumulative += float(t.get("realized_pnl", 0.0))
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
                
        return {
            "current_peak": peak,
            "max_drawdown": max_dd,
            "cumulative_pnl": cumulative
        }
