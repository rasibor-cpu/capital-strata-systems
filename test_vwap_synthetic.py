"""
test_vwap_synthetic.py | REA Capital
Purpose:
- Prove VWAP mean-reversion signal can fire
- Uses SYNTHETIC bars only (no market data)
- No execution, no persistence
"""

from datetime import datetime, timezone

from signals.vwap_mean_reversion import generate_vwap_mean_reversion_signals


def make_bar(ts, price, vol=1.0):
    """
    VWAP signal code expects dict bars with keys:
      ts_utc, h, l, c, v
    We'll set h=l=c=price for deterministic synthetic behavior.
    """
    return {
        "ts_utc": ts,
        "h": float(price),
        "l": float(price),
        "c": float(price),
        "v": float(vol),
    }


def main():
    now = datetime.now(timezone.utc)

    # Build synthetic bars hugging VWAP, then one sharp deviation
    prices = [
        100, 100.1, 99.9, 100.0, 100.05,
        100.0, 99.95, 100.0, 100.05, 100.0,
        102.5,   # <-- intentional deviation (should trigger)
    ]

    bars = [make_bar(now, p, vol=1.0) for p in prices]

    print("=" * 70)
    print("REA – Synthetic VWAP Signal Test")
    print("Bars supplied:", len(bars))
    print("=" * 70)

    signals = generate_vwap_mean_reversion_signals(
        bars_5m=bars,
