"""
OANDA 1-Year M5 Downloader (Paginated, Root-Safe)
Capital Strata Systems

Outputs canonical replay CSV:
    data/history/EUR_USD_M5_1year.csv

Format:
    timestamp,price

Notes:
- Uses OANDA REST v20
- Handles 5000-candle limit via pagination
- Saves relative to PROJECT ROOT, not current working directory
"""

from __future__ import annotations

import os
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================

# Practice (default). Change to LIVE only if you explicitly want live endpoint.
BASE_URL = "https://api-fxpractice.oanda.com/v3"

INSTRUMENT = "GBP_USD"
GRANULARITY = "M5"
PRICE = "M"          # M=mid, B=bid, A=ask
COUNT = 5000         # OANDA per-request max

# 1 year window
END = datetime.now(timezone.utc)
START = END - timedelta(days=365)

# =========================
# PATHS (ROOT-SAFE)
# =========================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = DATA_DIR / "history"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FILE = OUT_DIR / f"{INSTRUMENT}_{GRANULARITY}_1year.csv"

# =========================
# AUTH (ROOT-SAFE .env)
# =========================

# Always load from project root
load_dotenv(PROJECT_ROOT / ".env.practice")
API_TOKEN = os.getenv("OANDA_API_TOKEN")

if not API_TOKEN:
    raise Exception("Missing OANDA_API_TOKEN. Put it in .env.practice at project root.")

headers = {"Authorization": f"Bearer {API_TOKEN}"}
url = f"{BASE_URL}/instruments/{INSTRUMENT}/candles"

# =========================
# DOWNLOAD LOOP
# =========================

print(f"Downloading {INSTRUMENT} {GRANULARITY} from {START.isoformat()} to {END.isoformat()} ...")

rows = []
cursor = START
last_cursor = None

while cursor < END:
    params = {
        "from": cursor.isoformat().replace("+00:00", "Z"),
        "granularity": GRANULARITY,
        "price": PRICE,
        "count": COUNT,
    }

    resp = requests.get(url, headers=headers, params=params, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"OANDA error {resp.status_code}: {resp.text}")

    payload = resp.json()
    candles = payload.get("candles", [])

    if not candles:
        break

    # collect
    for c in candles:
        if not c.get("complete", False):
            continue
        mid = c.get("mid") or {}
        rows.append(
            {
                "timestamp": c["time"],
                "open": float(mid["o"]),
                "high": float(mid["h"]),
                "low": float(mid["l"]),
                "close": float(mid["c"]),
                "volume": int(c.get("volume", 0)),
            }
        )

    # advance cursor safely to avoid infinite loops
    last_time = candles[-1]["time"]  # ISO string
    cursor_dt = datetime.fromisoformat(last_time.replace("Z", "+00:00"))

    # if cursor doesn't move, force a jump by 1 minute to break loop
    if last_cursor is not None and cursor_dt <= last_cursor:
        cursor_dt = last_cursor + timedelta(minutes=5)

    last_cursor = cursor_dt
    cursor = cursor_dt + timedelta(seconds=1)

    print(f"Fetched up to {last_time} | Total rows: {len(rows)}")

    time.sleep(0.25)  # polite throttle

# =========================
# CLEAN + EXPORT (canonical replay format)
# =========================

df = pd.DataFrame(rows)
if df.empty:
    raise Exception("No candle data downloaded. Check instrument, token, and endpoint.")

# De-dup + sort
df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

# Canonical replay file: timestamp,price (use close)
replay = df[["timestamp", "close"]].rename(columns={"close": "price"})
replay.to_csv(OUT_FILE, index=False)

print("Download complete.")
print(f"Saved: {OUT_FILE}")
print(f"Rows: {len(replay)}")