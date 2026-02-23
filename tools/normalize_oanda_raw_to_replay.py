"""
Normalize OANDA Raw Minute/Month Files → Canonical M5 Replay File
Capital Strata Systems

Reads:
    data/gbpusd_raw/*.csv

Handles mixed timestamp formats, e.g.:
  - 2026-02-23T02:20:00.000000000Z
  - 01.01.2025 00:00:00 UTC

Outputs:
    data/history/GBP_USD_M5_1year.csv

Output format:
    timestamp,price
"""

import pandas as pd
from pathlib import Path


# =====================================================
# SAFE PROJECT ROOT RESOLUTION
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "gbpusd_raw"
OUTPUT_DIR = DATA_DIR / "history"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "GBP_USD_M5_1year.csv"

# Pandas-safe frequency string (avoid deprecated aliases like "5T")
RESAMPLE_FREQ = "5min"


def parse_utc_mixed(series: pd.Series) -> pd.Series:
    """
    Robust timestamp parser for mixed OANDA exports.
    Two-pass strategy:
      - Pass 1: general parse (handles ISO/Z)
      - Pass 2: dayfirst parse for 'dd.mm.yyyy ... UTC'
    """
    s = series.astype(str).str.strip()

    # Normalize suffix
    s = s.str.replace(" UTC", "", regex=False)

    # Pass 1: general parser (ISO/Z friendly)
    dt = pd.to_datetime(s, errors="coerce", utc=True)

    # Pass 2: dayfirst parser for European-style dates (01.01.2025 ...)
    mask = dt.isna()
    if mask.any():
        dt2 = pd.to_datetime(s[mask], errors="coerce", utc=True, dayfirst=True)
        dt.loc[mask] = dt2

    return dt


print("Loading raw CSV files...")

# =====================================================
# LOAD RAW FILES
# =====================================================

all_files = sorted(RAW_DIR.glob("*.csv"))
if not all_files:
    raise Exception("No raw CSV files found in data/gbpusd_raw")

dfs = []
for file in all_files:
    print(f"Reading {file.name}")
    df = pd.read_csv(file)

    # Schema check
    if "UTC" not in df.columns or "Close" not in df.columns:
        raise Exception(f"Unexpected columns in {file.name}. Need at least UTC and Close.")

    # Keep expected columns if present (some exports may omit Volume)
    keep = [c for c in ["UTC", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    dfs.append(df[keep])

data = pd.concat(dfs, ignore_index=True)

# =====================================================
# CLEAN + PARSE TIMESTAMPS
# =====================================================

data["UTC"] = parse_utc_mixed(data["UTC"])

bad = int(data["UTC"].isna().sum())
if bad:
    print(f"Warning: dropping {bad} rows with unparseable UTC timestamps.")
    data = data.dropna(subset=["UTC"])

data = data.sort_values("UTC")
data = data.drop_duplicates(subset=["UTC"])
data = data.set_index("UTC")

# Ensure numeric Close
data["Close"] = pd.to_numeric(data["Close"], errors="coerce")
data = data.dropna(subset=["Close"])

# =====================================================
# RESAMPLE TO M5
# =====================================================

print(f"Resampling to {RESAMPLE_FREQ}...")

agg_map = {
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
}
if "Volume" in data.columns:
    agg_map["Volume"] = "sum"

m5 = data.resample(RESAMPLE_FREQ).agg(agg_map)
m5 = m5.dropna(subset=["Close"])

# =====================================================
# EXPORT REPLAY FORMAT
# =====================================================

replay = pd.DataFrame({
    "timestamp": m5.index,
    "price": m5["Close"].astype(float),
}).reset_index(drop=True)

replay.to_csv(OUTPUT_FILE, index=False)

print("Normalization complete.")
print(f"Saved to: {OUTPUT_FILE}")
print(f"Rows: {len(replay)}")