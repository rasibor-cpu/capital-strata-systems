"""
OANDA Multi-Instrument Downloader (Paginated, Root-Safe)
Capital Strata Systems (CSS)

Writes one canonical replay CSV per instrument to:
    data/history/<INSTRUMENT>_<GRANULARITY>_1year.csv

Canonical replay format:
    timestamp,price

Notes:
- Uses OANDA REST v20
- Handles 5000-candle limit via pagination
- Saves relative to PROJECT ROOT, not current working directory
- Default endpoint: PRACTICE (api-fxpractice)
"""

from __future__ import annotations

import os
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd
from dotenv import load_dotenv


# -------------------------
# Core download
# -------------------------

def download_instrument(
    instrument: str,
    granularity: str,
    days: int,
    base_url: str,
    api_token: str,
    out_dir: Path,
    price: str = "M",
    count: int = 5000,
    throttle_s: float = 0.25,
) -> Path:
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{base_url}/instruments/{instrument}/candles"

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    out_file = out_dir / f"{instrument}_{granularity}_1year.csv"

    print(f"\n=== Downloading {instrument} {granularity} ({days}d) ===")
    print(f"Window: {start.isoformat()} -> {end.isoformat()}")

    rows = []
    cursor = start
    last_cursor = None

    while cursor < end:
        params = {
            "from": cursor.isoformat().replace("+00:00", "Z"),
            "granularity": granularity,
            "price": price,
            "count": count,
        }

        resp = requests.get(url, headers=headers, params=params, timeout=60)
        if resp.status_code != 200:
            raise Exception(f"OANDA error {resp.status_code} for {instrument}: {resp.text}")

        payload = resp.json()
        candles = payload.get("candles", [])
        if not candles:
            break

        for c in candles:
            if not c.get("complete", False):
                continue
            mid = c.get("mid") or {}
            rows.append(
                {
                    "timestamp": c["time"],
                    "close": float(mid["c"]),
                }
            )

        last_time = candles[-1]["time"]  # ISO string
        cursor_dt = datetime.fromisoformat(last_time.replace("Z", "+00:00"))

        # Safety: if cursor doesn't move, force step to break loops
        if last_cursor is not None and cursor_dt <= last_cursor:
            cursor_dt = last_cursor + timedelta(minutes=5)

        last_cursor = cursor_dt
        cursor = cursor_dt + timedelta(seconds=1)

        print(f"Fetched up to {last_time} | Total rows: {len(rows)}")
        time.sleep(throttle_s)

    df = pd.DataFrame(rows)
    if df.empty:
        raise Exception(f"No candle data downloaded for {instrument}. Check token, endpoint, instrument symbol.")

    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_file, index=False)

    print(f"Saved: {out_file}")
    print(f"Rows: {len(df)}")

    return out_file


# -------------------------
# CLI
# -------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--instruments",
        required=True,
        help='Comma-separated instruments, e.g. "EUR_USD,USD_JPY,AUD_USD"',
    )
    p.add_argument("--granularity", default="M5", help="OANDA granularity, default M5")
    p.add_argument("--days", type=int, default=365, help="Window length in days (default 365)")
    p.add_argument("--env", choices=["practice", "live"], default="practice", help="OANDA environment")
    p.add_argument("--out_dir", default="data/history", help="Output directory (relative to project root)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    project_root = Path(__file__).resolve().parents[1]
    out_dir = (project_root / args.out_dir).resolve()

    # Env selection
    if args.env == "practice":
        base_url = "https://api-fxpractice.oanda.com/v3"
        env_path = project_root / ".env.practice"
    else:
        base_url = "https://api-fxtrade.oanda.com/v3"
        env_path = project_root / ".env.live"

    load_dotenv(env_path)
    api_token = os.getenv("OANDA_API_TOKEN")
    if not api_token:
        raise Exception(f"Missing OANDA_API_TOKEN. Put it in {env_path.name} at project root.")

    instruments = [x.strip() for x in args.instruments.split(",") if x.strip()]
    if not instruments:
        raise Exception("No instruments parsed. Provide --instruments with comma-separated values.")

    print(f"Base URL: {base_url}")
    print(f"Out dir:  {out_dir}")
    print(f"Pairs:    {instruments}")

    for inst in instruments:
        download_instrument(
            instrument=inst,
            granularity=args.granularity,
            days=args.days,
            base_url=base_url,
            api_token=api_token,
            out_dir=out_dir,
        )

    print("\n=== DONE: Multi-instrument download complete ===")


if __name__ == "__main__":
    main()