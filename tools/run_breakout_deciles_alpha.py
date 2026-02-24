"""
Breakout Deciles Alpha – Volatility-Gated (Schema-Flexible)
Capital Strata Systems – Research Layer

Works with:
- OHLC CSVs (columns like open/high/low/close)
- Close-only CSVs (columns like price/close/c)

Volatility gate:
- Preferred: ATR(14) percentile over 100 bars (if OHLC exists)
- Fallback: abs(log return) percentile over 100 bars (if OHLC missing)

CLI:
  --csv <path>
  --lookback <int>
  --hold <int>
  --rank simple
Optional:
  --vol_gate 0.60
  --vol_window 100
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


# ---------------------------
# Column Normalization
# ---------------------------

def _lower_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _pick_first(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def load_prices(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = _lower_cols(df)

    # Try to map typical naming
    # Close
    close_col = _pick_first(df, [
        "close", "c", "price", "mid", "mid_c", "adj_close", "value"
    ])

    # High/Low (optional)
    high_col = _pick_first(df, ["high", "h", "mid_h"])
    low_col  = _pick_first(df, ["low", "l", "mid_l"])

    if close_col is None:
        raise ValueError(
            f"Cannot find a close/price column in {csv_path.name}. "
            f"Columns found: {list(df.columns)[:20]}"
        )

    # Standardize to close/high/low for downstream code
    out = pd.DataFrame()
    out["close"] = pd.to_numeric(df[close_col], errors="coerce")

    if high_col is not None and low_col is not None:
        out["high"] = pd.to_numeric(df[high_col], errors="coerce")
        out["low"] = pd.to_numeric(df[low_col], errors="coerce")
        out["_has_ohlc"] = True
    else:
        # Close-only mode
        out["high"] = out["close"]
        out["low"] = out["close"]
        out["_has_ohlc"] = False

    out = out.dropna().reset_index(drop=True)
    return out


# ---------------------------
# Volatility Measures
# ---------------------------

def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    # ATR requires high/low; if close-only, high==low==close => TR collapses to abs(close-close_prev)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr


def compute_abs_logret_vol(df: pd.DataFrame) -> pd.Series:
    # Works for close-only data
    r = np.log(df["close"]).diff().abs()
    return r


def rolling_percentile_last(x: np.ndarray) -> float:
    # Percentile rank of last value inside the window
    # Equivalent to rank(pct=True).iloc[-1], but faster/safer.
    if len(x) == 0 or np.all(np.isnan(x)):
        return np.nan
    s = pd.Series(x).dropna()
    if len(s) == 0:
        return np.nan
    last = s.iloc[-1]
    return float((s <= last).mean())


def compute_vol_percentile(df: pd.DataFrame, vol_window: int, prefer_atr: bool) -> tuple[pd.Series, str]:
    if prefer_atr:
        vol = compute_atr(df, 14)
        vol_pct = vol.rolling(vol_window).apply(lambda x: rolling_percentile_last(np.array(x)), raw=False)
        return vol_pct, "ATR14"
    else:
        vol = compute_abs_logret_vol(df)
        vol_pct = vol.rolling(vol_window).apply(lambda x: rolling_percentile_last(np.array(x)), raw=False)
        return vol_pct, "ABS_LOGRET"


# ---------------------------
# Breakout Signals
# ---------------------------

def generate_breakout_returns(df: pd.DataFrame, lookback: int, hold: int) -> list[float]:
    # Use close-based breakout by default (robust to close-only data)
    df = df.copy()
    df["roll_hi"] = df["close"].rolling(lookback).max()
    df["roll_lo"] = df["close"].rolling(lookback).min()

    rets: list[float] = []
    # start at lookback to avoid i-1 issues
    for i in range(lookback + 1, len(df) - hold):
        prev_hi = df["roll_hi"].iloc[i - 1]
        prev_lo = df["roll_lo"].iloc[i - 1]
        c = df["close"].iloc[i]
        exit_c = df["close"].iloc[i + hold]

        if np.isnan(prev_hi) or np.isnan(prev_lo):
            continue

        # Long breakout
        if c > prev_hi:
            rets.append(float(exit_c - c))
        # Short breakout
        elif c < prev_lo:
            rets.append(float(c - exit_c))

    return rets


def decile_stats(returns: list[float]) -> list[dict] | None:
    if len(returns) < 50:  # require enough signals for stability
        return None
    arr = np.array(returns, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 50:
        return None

    # Equal-population deciles by sorted return
    chunks = np.array_split(np.sort(arr), 10)
    out = []
    for d in chunks:
        out.append({
            "trades": int(len(d)),
            "exp": float(np.mean(d)) if len(d) else 0.0,
            "win": float(np.mean(d > 0)) if len(d) else 0.0,
        })
    return out


def monotonicity(stats: list[dict]) -> dict:
    exps = [s["exp"] for s in stats]
    non_dec = sum(exps[i] <= exps[i + 1] for i in range(9))
    return {
        "non_decreasing_steps": non_dec,
        "ratio": non_dec / 9,
        "d10_gt_d1": exps[-1] > exps[0],
        "d1": exps[0],
        "d10": exps[-1],
    }


# ---------------------------
# Main
# ---------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--lookback", type=int, default=30)
    ap.add_argument("--hold", type=int, default=6)
    ap.add_argument("--rank", default="simple")
    ap.add_argument("--vol_gate", type=float, default=0.60)
    ap.add_argument("--vol_window", type=int, default=100)
    args = ap.parse_args()

    csv_path = Path(args.csv)
    df = load_prices(csv_path)

    print(f"\nPrices loaded: {len(df)}")
    print(f"Lookback: {args.lookback}")
    print(f"Hold: {args.hold}")
    print(f"Rank mode: {args.rank}")

    prefer_atr = bool(df["_has_ohlc"].iloc[0])
    vol_pct, vol_mode = compute_vol_percentile(df, args.vol_window, prefer_atr=prefer_atr)

    df["vol_pct"] = vol_pct
    gated = df[df["vol_pct"] >= args.vol_gate].copy()

    print(f"Vol mode: {vol_mode} | Gate: vol_pct >= {args.vol_gate} | Window: {args.vol_window}")
    print(f"Bars after vol gate: {len(gated)}")

    rets = generate_breakout_returns(gated, args.lookback, args.hold)
    print(f"Signals captured: {len(rets)}")

    stats = decile_stats(rets)
    if stats is None:
        print("Not enough signals after gating to compute stable deciles.")
        return

    for i, s in enumerate(stats, start=1):
        print(f"D{i}: trades={s['trades']}, exp={s['exp']:.6e}, win={s['win']:.4f}")

    print("\nMonotonicity:")
    print(monotonicity(stats))


if __name__ == "__main__":
    main()