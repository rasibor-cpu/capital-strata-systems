"""
Confidence Scoring Engine for CSS Trading Intelligence Foundation
"""

from typing import Dict, Any

class ConfidenceEngine:
    """
    Computes advisor-level confidence indicators for trade candidates.
    """
    @staticmethod
    def calculate_confidence(candidate: Dict[str, Any], regime: str) -> float:
        """Derive 0.0-1.0 confidence score scaled by current volatility regime."""
        prob = float(candidate.get("probability", 0.5))
        
        modifier = 1.0
        if regime == "HIGH_VOLATILITY":
            modifier = 0.8
        elif regime == "RANGE_BOUND":
            modifier = 0.95
            
        score = prob * modifier
        return max(0.0, min(1.0, score))
