# capital_allocator.py
from audit_logger import CSSAuditLogger

class CapitalAllocator:
    def __init__(self):
        self.logger = CSSAuditLogger()
        self.max_slots = 10
        self.active_trades = [] # Track assets and performance

    def check_slot_availability(self):
        """Standard check for open diversification slots."""
        return len(self.active_trades) < self.max_slots

    def request_dynamic_reallocation(self, high_conviction_signal):
        """
        Institutional-grade pivot: identifies weak trades to close 
        in favor of a stronger opportunity.
        """
        if not self.active_trades:
            return False

        # Sort current trades by performance (PnL)
        weak_trade = min(self.active_trades, key=lambda x: x['pnl'])
        
        # Condition: Only pivot if new signal 'edge' > current weak performance
        if high_conviction_signal['expected_edge'] > abs(weak_trade['pnl']):
            self.logger.log_event(f"REALLOCATION: Closing weak {weak_trade['asset']} for {high_conviction_signal['asset']}")
            self.close_trade(weak_trade)
            return True
        
        return False

    def close_trade(self, trade):
        """Forces an exit on a weak asset to free a slot."""
        self.active_trades.remove(trade)
        self.logger.log_event(f"FORCE CLOSED: {trade['asset']} for capital recycling.")