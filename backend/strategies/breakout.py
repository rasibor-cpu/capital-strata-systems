def signal(candles, i):
    if i < 20:
        return False

    prior_highs = [c.high for c in candles[i - 20:i]]
    return candles[i].high > max(prior_highs)