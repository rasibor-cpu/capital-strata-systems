# capital_allocator.py
"""
CSS-GEMINI CAPITAL ALLOCATOR
Enhanced with Asymmetric Exit Logic and Trailing Stop-Losses.
"""
from audit_logger import get_audit

class CapitalAllocator:
    def __init__(self):
        self.audit = get_audit()
        self.max_slots = 10
        self.active_trades = [] 
        self.hard_stop_pct = 0.02  # 2% Max Loss
        self.trail_activation_pct = 0.01 # Start trailing at 1% profit

    def check_slot_availability(self) -> bool:
        return len(self.active_trades) < self.max_slots

    def update_trailing_stops(self, market_data: dict):
        """
        Adjusts exit points dynamically. 
        If a trade is in profit, it 'locks' a portion of that gain.
        """
        for trade in self.active_trades:
            symbol = trade['asset']
            current_price = market_data.get(symbol)
            pnl = (current_price - trade['entry']) / trade['entry']

            if pnl > self.trail_activation_pct:
                # Tighten stop-loss to 0.5% below current price
                new_sl = current_price * 0.995
                if new_sl > trade.get('sl', 0):
                    trade['sl'] = new_sl
                    self.audit.log("STOP_TIGHTENED", "allocator", {"asset": symbol, "new_sl": new_sl})

    def request_dynamic_reallocation(self, signal: dict) -> bool:
        """Recycles capital from the weakest performer to high-edge signals."""
        if not self.active_trades: return False

        weak_trade = min(self.active_trades, key=lambda x: x.get('pnl', 0))
        
        if signal.get('expected_edge', 0) > abs(weak_trade.get('pnl', 0)):
            self.audit.log("CAPITAL_REALLOCATED", "allocator", {"from": weak_trade['asset'], "to": signal['asset']})
            self.close_trade(weak_trade, "REALLOCATION")
            return True
        return False

    def close_trade(self, trade: dict, reason: str):
        if trade in self.active_trades:
            self.active_trades.remove(trade)
            self.audit.position_closed(trade['asset'], trade.get('pnl', 0), reason, 98.0199)