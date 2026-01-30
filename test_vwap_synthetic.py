"""
test_vwap_synthetic.py | REA Capital
Purpose:
- Prove VWAP mean-reversion signal can fire
- Uses SYNTHETIC bars only (no market data)
- No execution, no persistence
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from signals.vwap_mean_reversion import generate_vwap_mean_reversion_signals


def make_bar(ts, price, vol=1.0):
    return SimpleNamespace(
        ts_utc=ts,
        o=price,
        h=price,
        l=price,
        c=price,
        v=vol,
    )


def main():
    now = datetime.now(timezone.utc)

    # Build synthetic bars hugging VWAP, then one sharp deviation
    prices = [
        100, 100.1, 99.9, 100.0, 100.05,
        100.0, 99.95, 100.0, 100.05, 100.0,
        102.5,   # <-- intentional deviation (should trigger)
    ]

    bars = []
    for i, p in enumerate(prices):
        bars.append(make_bar(now, p))

    print("=" * 70)
    print("REA – Synthetic VWAP Signal Test")
    print("Bars supplied:", len(bars))
    print("=" * 70)

    signals = generate_vwap_mean_reversion_signals(
        bars_5m=bars,
        lookback=10,
        threshold=1.0,   # permissive but not forced
    )

    print("\n[Signals Returned]")
    for s in signals:
        print(s)

    if not signals:
        print("\nNO SIGNALS — investigate")
    else:
        print("\nSUCCESS — VWAP signal fired")

    print("\nDone.")


if __name__ == "__main__":
    main()
