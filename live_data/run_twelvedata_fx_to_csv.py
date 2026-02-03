from __future__ import annotations

"""
REA Capital – Live FX Feed (Twelve Data -> CSV)
- Polls Twelve Data quote endpoint for selected FX pairs
- Writes append-only CSV in REA-friendly schema:
  timestamp,pair,bid,ask,mid,source
- Designed for prompt-only research workflows (NO execution)

ENV:
  TWELVEDATA_API_KEY   (required)
OPTIONAL ENV:
  REA_TD_PAIRS         default: "EUR/USD,USD/JPY,GBP/USD"
  REA_TD_INTERVAL_SEC  default: "10"
  REA_TD_OUT_CSV       default: "data/fx_pairs.csv"

Run:
  set TWELVEDATA_API_KEY=your_key_here
  python live_data\run_twelvedata_fx_to_csv.py
"""

import os
import csv
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import urllib.parse
import urllib.request
import json


TD_QUOTE_URL = "https://api.twelvedata.com/quote"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(",", "")
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


def _http_get_json(url: str, params: Dict[str, str], timeout: int = 15) -> Dict[str, Any]:
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}"
    req = urllib.request.Request(full, headers={"User-Agent": "REA-TwelveData-Client/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def _parse_quote(payload: Dict[str, Any]) -> Dict[str, float]:
    """
    Twelve Data 'quote' responses vary by instrument.
    For FX we try bid/ask if present; otherwise fallback to price/close.
    """
    bid = _safe_float(payload.get("bid"))
    ask = _safe_float(payload.get("ask"))

    # fallback keys
    price = _safe_float(payload.get("price"))
    close = _safe_float(payload.get("close"))

    if bid == 0.0 and ask == 0.0:
        mid = price or close
        if mid == 0.0:
            return {"bid": 0.0, "ask": 0.0, "mid": 0.0}
        return {"bid": mid, "ask": mid, "mid": mid}

    mid = (bid + ask) / 2.0 if (bid and ask) else (bid or ask)
    return {"bid": bid or mid, "ask": ask or mid, "mid": mid}


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _write_csv_row(out_csv: str, row: Dict[str, Any]) -> None:
    _ensure_parent_dir(out_csv)
    file_exists = os.path.exists(out_csv)

    headers = ["timestamp", "pair", "bid", "ask", "mid", "source"]
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            w.writeheader()
        w.writerow(row)


def main() -> int:
    api_key = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing env var TWELVEDATA_API_KEY")

    pairs_raw = os.getenv("REA_TD_PAIRS", "EUR/USD,USD/JPY,GBP/USD").strip()
    pairs = [p.strip().upper() for p in pairs_raw.split(",") if p.strip()]
    if not pairs:
        raise RuntimeError("No pairs configured. Set REA_TD_PAIRS, e.g. EUR/USD,USD/JPY")

    interval_sec = int(_safe_float(os.getenv("REA_TD_INTERVAL_SEC", "10"), 10.0))
    interval_sec = max(3, min(interval_sec, 60))  # keep sane

    out_csv = os.getenv("REA_TD_OUT_CSV", "data/fx_pairs.csv").strip()
    if not out_csv:
        out_csv = "data/fx_pairs.csv"

    print("REA Twelve Data FX -> CSV")
    print("-" * 72)
    print("pairs:", ",".join(pairs))
    print("interval_sec:", interval_sec)
    print("out_csv:", out_csv)
    print("-" * 72)
    print("CTRL+C to stop.\n")

    backoff = 0
    while True:
        try:
            for pair in pairs:
                params = {
                    "symbol": pair,
                    "apikey": api_key,
                }
                payload = _http_get_json(TD_QUOTE_URL, params=params, timeout=15)

                # TwelveData error format often includes: {"code":..., "message":"..."}
                if "message" in payload and ("code" in payload or "status" in payload):
                    msg = str(payload.get("message", "unknown error"))
                    raise RuntimeError(f"TwelveData error for {pair}: {msg}")

                q = _parse_quote(payload)
                if q["mid"] == 0.0:
                    print(f"[WARN] {pair}: quote missing/zero -> payload keys: {list(payload.keys())}")
                    continue

                row = {
                    "timestamp": _utc_iso(),
                    "pair": pair,
                    "bid": f"{q['bid']:.6f}",
                    "ask": f"{q['ask']:.6f}",
                    "mid": f"{q['mid']:.6f}",
                    "source": "twelvedata",
                }
                _write_csv_row(out_csv, row)
                print(f"[OK] {row['timestamp']} {pair} mid={row['mid']}")

            backoff = 0
            time.sleep(interval_sec)

        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

        except Exception as e:
            backoff = 5 if backoff == 0 else min(backoff * 2, 60)
            print(f"[ERROR] {e} | backing off {backoff}s")
            time.sleep(backoff)


if __name__ == "__main__":
    raise SystemExit(main())
