# orchestrator.py
"""
CAPITAL STRATA SYSTEMS (CSS) - CORE ORCHESTRATOR
Integrated with Operational Firewall and Liquidity Guardrails.
"""

from gemini_regime_detector import MarketRegimeDetector
from gemini_context_gate import IntermarketContextGate
from gemini_momentum_sync import GeminiMomentumSync
from gemini_liquidity_filter import LiquidityFilter
from security_gate import SecurityGate
from capital_allocator import CapitalAllocator
from audit_logger import get_audit

class TradeDecisionOrchestrator:
    def __init__(self):
        self.security = SecurityGate()
        self.liquidity = LiquidityFilter()
        self.regime_detector = MarketRegimeDetector()
        self.context_gate = IntermarketContextGate()
        self.momentum_sync = GeminiMomentumSync()
        self.allocator = CapitalAllocator()
        self.audit = get_audit()
        self.ssot_balance = 98.0199 

    def pre_trade_validation(self, signal):
        """Sequential multi-layer validation for capital protection."""
        symbol = signal.get('asset', 'UNKNOWN')
        
        # 1. Operational Firewall: check_system_integrity()
        if not self.security.check_system_integrity():
            return False

        # 2. Liquidity Filter: check volume floor
        if not self.liquidity.has_sufficient_liquidity(symbol, signal.get('vol', 2000000)):
            return False

        # 3. Intelligence Gates: Regime & Macro Context
        if not self.regime_detector.is_regime_favorable(signal.get('strategy')):
            return False

        if not self.context_gate.allow_execution(signal):
            return False

        # 4. Governance: Slot Capacity & Dynamic Reallocation
        if not self.allocator.check_slot_availability():
            if self.allocator.request_dynamic_reallocation(signal):
                return True
            return False

        return True

    def run_alpha_cycle(self):
        """Primary Engine Loop."""
        # Final safety check before boot
        if not self.security.check_system_integrity():
            print("[HALTED] Engine cannot start. Check security gate.")
            return
        
        self.audit.log("ENGINE_START", "orchestrator", {"balance": self.ssot_balance})
        
        signals = self.momentum_sync.get_signals()
        for sig in signals:
            if self.pre_trade_validation(sig):
                self.execute_trade(sig)

    def execute_trade(self, signal):
        """Execution at SSoT reference level."""
        self.audit.trade_executed(
            symbol=signal.get('asset'), 
            side=signal.get('side', 'BUY'), 
            qty=1.0, 
            price=0, 
            sl=0, 
            tp=0, 
            cost_bps=0.1
        )

if __name__ == "__main__":
    TradeDecisionOrchestrator().run_alpha_cycle()