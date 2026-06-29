"""
Portfolio Risk and Concentration Analyzer for CSS Trading Intelligence Foundation
"""

from typing import Dict, Any

class PortfolioAnalyzer:
    """
    Measures portfolio balance, asset concentrations, and risk weights.
    """
    @staticmethod
    def calculate_concentration(portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
        """Determine asset percentages and derived concentration risk score."""
        total = sum(abs(float(v)) for v in portfolio_state.values())
        concentrations = {}
        if total == 0:
            return {"concentrations": {}, "highest_exposure_asset": "NONE", "risk_concentration_score": 0.0}
        
        highest_asset = "NONE"
        max_pct = 0.0
        for k, v in portfolio_state.items():
            pct = abs(float(v)) / total
            concentrations[k] = pct
            if pct > max_pct:
                max_pct = pct
                highest_asset = k
                
        risk_score = max_pct * 100.0
        
        return {
            "concentrations": concentrations,
            "highest_exposure_asset": highest_asset,
            "risk_concentration_score": risk_score
        }
