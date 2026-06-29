"""
Performance Analyzer for CSS Trading Intelligence Foundation
"""

from typing import List, Dict, Any

class PerformanceAnalyzer:
    """
    Groups and parses historical trades to determine asset performance.
    """
    @staticmethod
    def calculate_asset_class_performance(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate trade stats and total PnL per asset class."""
        perf = {}
        for t in trades:
            aclass = str(t.get("asset_class", "UNKNOWN")).upper()
            pnl = float(t.get("realized_pnl", 0.0))
            if aclass not in perf:
                perf[aclass] = {"trades_count": 0, "total_pnl": 0.0, "wins": 0}
            perf[aclass]["trades_count"] += 1
            perf[aclass]["total_pnl"] += pnl
            if pnl > 0:
                perf[aclass]["wins"] += 1
        return perf
