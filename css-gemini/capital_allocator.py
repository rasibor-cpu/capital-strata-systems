# capital_allocator.py
"""
CSS-GEMINI CAPITAL ALLOCATOR
Institutional slot management and dynamic reallocation logic.
Synced with Singleton AuditLogger.
"""
from audit_logger import get_audit

class CapitalAllocator:
    def __init__(self):
        # Sync with the global audit singleton
        self.audit = get_audit()
        self.max_slots = 10
        self.active_trades = [] 

    def check_slot_availability(self) -> bool:
        """Ensures the engine stays within the 10-trade diversification limit."""
        return len(self.active_trades) < self.max_slots

    def request_dynamic_reallocation(self, signal: dict) -> bool:
        """
        Identifies weak trades to recycle capital for higher-conviction signals.
        Helps protect the $98.0199 SSoT balance.
        """
        if not self.active_trades:
            return False

        # Simple logic: find the trade with the lowest PnL
        weak_trade = min(self.active_trades, key=lambda x: x.get('pnl', 0))
        
        # If new signal has higher expected edge, recycle the capital
        if signal.get('expected_edge', 0) > abs(weak_trade.get('pnl', 0)):
            self.audit.log("CAPITAL_REALLOCATED", "capital_allocator", 
                           {"from": weak_trade['asset'], "to": signal['asset']})
            self.close_trade(weak_trade)
            return True
        
        return False

    def close_trade(self, trade: dict):
        """Standard exit procedure."""
        if trade in self.active_trades:
            self.active_trades.remove(trade)
            self.audit.position_closed(
                symbol=trade['asset'], 
                pnl=trade.get('pnl', 0), 
                reason="REALLOCATION", 
                capital=98.0199
            )