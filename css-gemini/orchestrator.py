# orchestrator.py
"""
CAPITAL STRATA SYSTEMS (CSS) - CORE ORCHESTRATOR
Institutional-grade execution engine with dynamic capital reallocation.
Reference Balance: 98.0199 SSoT
"""

from gemini_regime_detector import MarketRegimeDetector
from gemini_context_gate import IntermarketContextGate
from gemini_momentum_sync import GeminiMomentumSync
from capital_allocator import CapitalAllocator
from audit_logger import CSSAuditLogger

class TradeDecisionOrchestrator:
    def __init__(self):
        # 1. Intelligence Layer Initialization
        self.regime_detector = MarketRegimeDetector()
        self.context_gate = IntermarketContextGate()
        self.momentum_sync = GeminiMomentumSync()
        
        # 2. Governance & Allocation Initialization
        self.allocator = CapitalAllocator()
        self.logger = CSSAuditLogger()
        self.ssot_balance = 98.0199  # Single Source of Truth for capital alignment

    def pre_trade_validation(self, signal):
        """
        Multi-stage institutional filter to protect $98.0199 capital.
        Stages: Regime -> Context -> Capacity/Reallocation
        """
        
        # STAGE 1: Market Regime Analysis
        if not self.regime_detector.is_regime_favorable(signal.get('strategy')):
            self.logger.log_event(f"REJECTED: Regime mismatch for {signal['asset']}")
            return False

        # STAGE 2: Intermarket Context Gate
        if not self.context_gate.allow_execution(signal):
            self.logger.log_event(f"REJECTED: Context Gate block for {signal['asset']}")
            return False

        # STAGE 3: Capacity Management & Dynamic Reallocation
        if not self.allocator.check_slot_availability():
            # Trigger 'Hunting' mode: Can we recycle capital from a weak asset?
            if self.allocator.request_dynamic_reallocation(signal):
                self.logger.log_event(f"REALLOCATION SUCCESS: Recycled slot for high-conviction {signal['asset']}")
                return True
            else:
                self.logger.log_event("REJECTED: Capacity (10 slots) full with no weak trades to exit.")
                return False

        return True

    def run_alpha_cycle(self):
        """Main execution loop for processing Gemini Alpha signals."""
        self.logger.log_event("SYSTEM: Starting Alpha Intelligence Cycle.")
        
        signals = self.momentum_sync.get_signals()
        for sig in signals:
            if self.pre_trade_validation(sig):
                self.execute_trade(sig)

    def execute_trade(self, signal):
        """Final execution execution at the broker level."""
        self.logger.log_event(f"EXECUTING: {signal['asset']} position based on $SSOT_BALANCE.")
        # Logic for diversified execution across FX, Crypto, and Futures goes here.

if __name__ == "__main__":
    # Boot up the engine
    engine = TradeDecisionOrchestrator()
    engine.run_alpha_cycle()