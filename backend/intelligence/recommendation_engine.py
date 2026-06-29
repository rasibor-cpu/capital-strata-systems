"""
Recommendation Engine for CSS Trading Intelligence Foundation
"""

from typing import List, Dict, Any

class RecommendationEngine:
    """
    Formulates operational recommendations based on active risk indicators.
    """
    @staticmethod
    def generate_recommendations(
        concentration_info: Dict[str, Any],
        win_loss_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Evaluate portfolio metrics to construct warning and informational tips."""
        recs = []
        
        risk_score = concentration_info.get("risk_concentration_score", 0.0)
        highest_asset = concentration_info.get("highest_exposure_asset", "NONE")
        if risk_score > 40.0:
            recs.append({
                "type": "PORTFOLIO_DIVERSIFICATION",
                "priority": "HIGH",
                "message": f"Asset class {highest_asset} accounts for {risk_score:.1f}% of total exposure. Recommend diversifying to mitigate concentration risk."
            })
            
        win_rate = win_loss_info.get("win_rate", 1.0)
        if win_rate < 0.4 and win_loss_info.get("total_trades", 0) >= 5:
            recs.append({
                "type": "STRATEGY_COOLDOWN",
                "priority": "WARNING",
                "message": f"Strategy win rate has fallen to {win_rate*100:.1f}%. Recommend reviewing recent trades and adjusting allocation sizes."
            })
            
        if not recs:
            recs.append({
                "type": "PORTFOLIO_HEALTHY",
                "priority": "INFO",
                "message": "Concentration and win rate indexes are within healthy bounds. No immediate adjustments needed."
            })
            
        return recs
