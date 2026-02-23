"""
tools/generate_regime_replay_csv.py

Deterministic expanded replay dataset generator.
Creates CSV: timestamp,price

Usage:
python tools\generate_regime_replay_csv.py --out data\replay_usdgbp_10k.csv --bars 10000 --seed 42
"""

from __future__ import annotations
import argparse
import csv
from datetime import datetime, timedelta, timezone
from random import Random


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--bars", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = Random(args.seed)

    start_price = 1.2700
    price = start_price
    t = datetime(2025, 1, 1, tzinfo=timezone.utc)
    dt = timedelta(minutes=5)

    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "price"])

        regime_length = 0
        regime_type = "trend"

        for i in range(args.bars):

            # Change regime occasionally
            if regime_length <= 0:
                regime_type = rng.choice(["trend_up", "trend_down", "mean_revert", "chop"])
                regime_length = rng.randint(200, 1200)

            regime_length -= 1

            noise = (rng.random() - rng.random()) * 0.0005

            if regime_type == "trend_up":
                drift = 0.00002
            elif regime_type == "trend_down":
                drift = -0.00002
            elif regime_type == "mean_revert":
                drift = (start_price - price) * 0.05
            else:
                drift = 0

            price += drift + noise
            price = round(max(price, 0.0001), 5)

            writer.writerow([t.isoformat().replace("+00:00", "Z"), price])
            t += dt

    print(f"OK: wrote {args.bars} bars to {args.out}")


if __name__ == "__main__":
    main()