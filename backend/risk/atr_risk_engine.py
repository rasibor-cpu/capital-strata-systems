from typing import List


class ATRRiskEngine:

    def __init__(self, period: int = 14):
        self.period = period

    def compute_atr(self, candles: List, i: int):

        if i < self.period:
            return None

        trs = []

        for j in range(i - self.period + 1, i + 1):

            high = candles[j].high
            low = candles[j].low
            prev_close = candles[j - 1].close

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )

            trs.append(tr)

        return sum(trs) / len(trs)

    def stop_loss(self, entry_price, atr):

        return entry_price - (1.5 * atr)

    def take_profit(self, entry_price, atr):

        return entry_price + (2.5 * atr)