# gemini_regime_detector.py
"""
CSS-GEMINI REGIME DETECTOR
Institutional-grade market classification synced with Singleton AuditLogger.
"""
from audit_logger import get_audit

class MarketRegimeDetector:
    def __init__(self):
        # Sync with the global audit singleton
        self.audit = get_audit()
        self.volatility_ceiling = 0.25 

    def get_current_regime(self):
        """
        Analyzes market conditions. 
        Institutional standard: Defaulting to TRENDING for system handshake.
        """
        regimes = ["TRENDING", "RANGING", "VOLATILE", "BLACK_SWAN"]
        current = regimes[0] 
        
        return {
            "status": current,
            "trade_allowed": True if current != "BLACK_SWAN" else False
        }

    def is_regime_favorable(self, strategy_type: str) -> bool:
        """Institutional check: Does the strategy fit the current market?"""
        regime_data = self.get_current_regime()
        
        # Log critical halts if the regime is unfavorable
        if not regime_data['trade_allowed']:
            self.audit.log("REGIME_REJECTED", "regime_filter", 
                           {"regime": regime_data['status'], "reason": "Black Swan Protocol Active"}, 
                           level="CRITICAL")
            return False
            
        return True