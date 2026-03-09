class PositionSizingEngine:

    def __init__(self, risk_pct=0.01):
        self.risk_pct = risk_pct

    def size_position(self, capital, entry_price, atr):

        if atr is None or atr == 0:
            return 0

        risk_amount = capital * self.risk_pct

        position_size = risk_amount / atr

        return position_size