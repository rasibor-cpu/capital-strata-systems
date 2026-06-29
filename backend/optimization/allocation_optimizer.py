"""
Allocation Exposure Optimizer for CSS Trading Optimization Framework
"""

from typing import Dict, Any

class AllocationOptimizer:
    """
    Evaluates allocation concentrations to advise on exposure limits.
    """
    @staticmethod
    def optimize_allocation(concentration_info: Dict[str, Any]) -> Dict[str, Any]:
        """Advise limits when single asset exposure exceeds target threshold."""
        risk_score = concentration_info.get("risk_concentration_score", 0.0)
        highest_asset = concentration_info.get("highest_exposure_asset", "NONE")
        
        target_allocation = {}
        if risk_score > 40.0:
            target_allocation[highest_asset] = 0.30
            target_allocation["OTHER"] = 0.70
            action = f"Cap {highest_asset} allocation at 30% to improve balance."
        else:
            target_allocation[highest_asset] = 0.50
            target_allocation["OTHER"] = 0.50
            action = "Keep current target allocations."
            
        return {
            "target_allocation": target_allocation,
            "action_recommendation": action
        }
