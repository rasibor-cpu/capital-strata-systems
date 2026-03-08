def signal(candles, i):
    if i < 10:
        return False

    fast_ma = sum(c.close for c in candles[i - 3:i]) / 3.0
    slow_ma = sum(c.close for c in candles[i - 10:i]) / 10.0

    return fast_ma > slow_ma