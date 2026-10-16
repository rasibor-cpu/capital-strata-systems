"""Market-data provider matrix: static readiness plus an optional live, read-only probe.

Usage:
  python tools/css_market_data_matrix.py                       # static: credentials / jurisdiction only
  CSS_OPERATING_COUNTRY=CA python tools/css_market_data_matrix.py --probe --out evidence/market_data_matrix.json

A provider is PASS only when the probe fetched validated, fresh, complete bars from the real
endpoint during this run. Anything else is BLOCKED with the exact reason (missing credential,
jurisdiction, HTTP status, network refusal, stale data). Nothing here places an order, and no
credential value is ever written to the output.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.signals.candles import CandleError, check_fresh  # noqa: E402
from backend.signals import market_data as md  # noqa: E402

PROBE_INSTRUMENT = {"coinbase": "BTC-USD", "alpaca_crypto": "BTC-USD", "binance": "BTC-USDT",
                    "alpaca_stock": "SPY", "oanda": "EUR_USD"}
QUOTES = {"coinbase": md.CoinbaseQuotes, "alpaca_crypto": md.AlpacaCryptoQuotes}


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def probe_provider(name: str, *, granularity_s: int, now: datetime, http=None) -> dict[str, Any]:
    out: dict[str, Any] = {"name": name, "instrument": PROBE_INSTRUMENT.get(name)}
    try:
        provider = md.build_provider(name, http=http)
        series = provider.fetch(PROBE_INSTRUMENT[name], granularity_s=granularity_s)
    except (CandleError, OSError, ValueError) as exc:
        return {**out, "verdict": "BLOCKED", "reason": str(exc)}
    out.update(source=series.source, classification=series.classification, bars=len(series.candles),
               data_sha256=series.digest)
    if not series.candles:
        return {**out, "verdict": "BLOCKED", "reason": "no_candles_returned"}
    out["last_bar_open_utc"] = datetime.fromtimestamp(series.candles[-1].ts, tz=timezone.utc).isoformat()
    out["last_close"] = series.candles[-1].close
    try:
        m = md.series_metrics(series)
        out["metrics"] = {"completeness": round(m.completeness, 4), "realised_vol_bps_per_bar": round(m.realised_vol_bps, 2),
                          "median_volume": m.median_volume, "zero_volume_bars": m.zero_volume_bars}
    except CandleError as exc:
        out["metrics_error"] = str(exc)
    try:
        # Equities trade in sessions: a closed market is reported, not treated as fresh.
        check_fresh(series, now=now, max_bars_stale=2)
        out["fresh"] = True
    except CandleError as exc:
        out["fresh"] = False
        out["freshness_reason"] = str(exc)
    if name in QUOTES:
        try:
            q = QUOTES[name](http or md.resilient_http()).quote(PROBE_INSTRUMENT[name])
            out["quote"] = {"bid": q.bid, "ask": q.ask, "spread_bps": round(q.spread_bps, 3),
                            "bid_depth_25bps": q.bid_depth_notional, "ask_depth_25bps": q.ask_depth_notional,
                            "exchange_time": q.exchange_ts.isoformat()}
        except (CandleError, OSError, ValueError) as exc:
            out["quote_error"] = str(exc)
    out["verdict"] = "PASS" if out.get("fresh") else "BLOCKED"
    if not out.get("fresh"):
        out["reason"] = out.get("freshness_reason", "not_fresh")
    out["_series"] = series
    return out


def run(*, probe: bool, granularity_s: int = 3600, env=None, http=None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    static = md.provider_matrix(env)
    report: dict[str, Any] = {
        "generated_utc": now.isoformat(), "code_revision": _git_head(), "probe": probe,
        "operating_country": (dict(os.environ if env is None else env).get("CSS_OPERATING_COUNTRY") or "").upper() or None,
        "static": static, "providers": {}, "cross_provider": None, "clock_skew": None,
        "paper_only": True, "orders_placed": 0,
    }
    if not probe:
        return report
    by_source = {r["provider"]: r for r in static}
    series = {}
    for name in md.PROVIDER_NAMES:
        src = md.SOURCE_BY_NAME.get(name)
        row = by_source.get(src) if src else by_source.get(f"blocked_{name}")
        if row is None or row["status"] != "READY":
            report["providers"][name] = {"name": name, "verdict": "BLOCKED", "reason": (row or {}).get("reason", "unknown")}
            continue
        result = probe_provider(name, granularity_s=granularity_s, now=now, http=http)
        if "_series" in result:
            series[name] = result.pop("_series")
        report["providers"][name] = result
    if "coinbase" in series and "alpaca_crypto" in series:
        try:
            d = md.compare_series(series["coinbase"], series["alpaca_crypto"])
            report["cross_provider"] = {"pair": "coinbase BTC-USD vs alpaca_crypto BTC/USD", "overlap_bars": d.overlap_bars,
                                        "max_bps": round(d.max_bps, 3), "median_bps": round(d.median_bps, 3),
                                        "last_bps": round(d.last_bps, 3)}
        except CandleError as exc:
            report["cross_provider"] = {"error": str(exc)}
    try:
        skew = md.measure_clock_skew(md.coinbase_server_time(http or md.resilient_http()))
        report["clock_skew"] = {"reference": "coinbase /time", "skew_s": round(skew, 3),
                                "within_5s": abs(skew) <= 5.0}
    except (CandleError, OSError, ValueError, KeyError) as exc:
        report["clock_skew"] = {"error": str(exc)}
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="contact the real read-only endpoints")
    ap.add_argument("--granularity", type=int, default=3600)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    report = run(probe=args.probe, granularity_s=args.granularity)
    text = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    for name, row in report["providers"].items():
        print(f"{name:14s} {row['verdict']:8s} {row.get('reason') or row.get('classification', '')}")
    if not report["providers"]:
        for row in report["static"]:
            print(f"{row['provider']:26s} {row['status']:8s} {row['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
