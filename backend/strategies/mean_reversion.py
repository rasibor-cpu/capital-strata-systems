def signal(candles, i):
    if i < 5:
        return False

    avg_close = (
        candles[i - 1].close +
        candles[i - 2].close +
        candles[i - 3].close +
        candles[i - 4].close +
        candles[i - 5].close
    ) / 5.0

    return candles[i].close < avg_close * 0.995