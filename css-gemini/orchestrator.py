# orchestrator.py
from gemini_regime_detector import MarketRegimeDetector
from gemini_context_gate import IntermarketContextGate
from gemini_momentum_sync import GeminiMomentumSync
from capital_allocator import CapitalAllocator
from audit_logger import CSSAuditLogger

class TradeDecisionOrchestrator:
    def __init__(self):
        # Initialize the Intelligence Layer
        self.regime_detector = MarketRegimeDetector()
        self.context_gate = IntermarketContextGate()
        self.momentum_sync = GeminiMomentumSync()
        
        # Initialize Governance & Allocation
        self.allocator = CapitalAllocator()
        self.logger = CSSAuditLogger()
        self.ssot_balance = 98.0199 # Single Source of Truth

    def pre_trade_validation(self, signal):
        """Institutional-grade filtering for capital protection."""
        
        # 1. Regime Detection: Only trade in aligned market conditions
        if not self.regime_detector.is_regime_favorable(signal['strategy']):
            self.logger.log_event(f"REJECTED: Regime mismatch for {signal['asset']}")
            return False

        # 2. Context Gate: Check Macro/Intermarket headwinds
        if not self.context_gate.allow_execution(signal):
            self.logger.log_event(f"REJECTED: Context Gate block for {signal['asset']}")
            return False

        # 3. Capacity Check: Enforce 10-trade cycle limit
        if not self.allocator.check_slot_availability():
            self.logger.log_event("REJECTED: Maximum portfolio diversification reached (10 slots)")
            return False

        return True

    def run_alpha_cycle(self):
        """Primary execution loop for the Gemini Alpha Engine."""
        signals = self.momentum_sync.get_signals()
        for sig in signals:
            if self.pre_trade_validation(sig):
                self.execute_trade(sig)

    def execute_trade(self, signal):
        self.logger.log_event(f"EXECUTING: {signal['asset']} at $SSOT_BALANCE reference.")