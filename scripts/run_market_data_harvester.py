from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import CoinbaseHistoricalDownloader


ASSETS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "LINK-USD",
    "AVAX-USD",
]


GRANULARITY = "FIFTEEN_MINUTE"
DAYS = 7


def main():

    print("\n====== CSS Multi-Asset Data Harvester ======\n")

    downloader = CoinbaseHistoricalDownloader()

    downloaded = []

    for asset in ASSETS:

        print(f"\nDownloading candles for {asset}")

        candles = downloader.download_range(
            product_id=asset,
            granularity=GRANULARITY,
            days=DAYS,
        )

        path = downloader.save_to_csv(
            candles=candles,
            product_id=asset,
            granularity=GRANULARITY,
            days=DAYS,
        )

        print(f"Saved dataset → {path}")

        downloaded.append(path.name)

    print("\nDownload Summary\n")

    for d in downloaded:
        print("✔", d)

    print("\nDatasets ready for batch backtesting.\n")


if __name__ == "__main__":
    main()