from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.opportunity_pressure_trigger import OpportunityPressureTrigger
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

SCAN_INTERVAL = int(os.getenv("CSS_SCAN_INTERVAL_SECONDS", "10"))
SEED_COUNT = int(os.getenv("CSS_SEED_ASSET_COUNT", "5"))
MAX_DISPLAY = 5

BASE_ASSETS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "AVAX-USD",
    "LINK-USD",
]

scanner = UnifiedMarketScanner()
feature_builder = FeatureBuilder()
pressure_engine = OpportunityPressureEngine()
pressure_trigger = OpportunityPressureTrigger()
ai = AIOpportunityScorer()

vwap_cfg = VWAPConfig()

capital = 200.0
cycle = 0


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _normalize_candles(candles: List[Any]) -> List[Dict[str, float]]:
    normalized: List[Dict[str, float]] = []

    for c in candles:
        try:
            normalized.append(
                {
                    "open": _to_float(getattr(c, "open", 0.0)),
                    "high": _to_float(getattr(c, "high", 0.0)),
                    "low": _to_float(getattr(c, "low", 0.0)),
                    "close": _to_float(getattr(c, "close", 0.0)),
                    "volume": _to_float(getattr(c, "volume", 0.0)),
                }
            )
        except Exception:
            continue

    return [c for c in normalized if c["close"] > 0]


def discover_coinbase_symbols() -> List[str]:

    try:
        discovered = scanner.scan()
    except Exception:
        discovered = []

    symbols: List[str] = []
    seen = set()

    for item in discovered:

        if not isinstance(item, dict):
            continue

        venue = str(item.get("venue", "")).upper()
        symbol = str(item.get("symbol", "")).upper()

        if venue != "COINBASE":
            continue

        if symbol in seen:
            continue

        symbols.append(symbol)
        seen.add(symbol)

    if not symbols:
        return BASE_ASSETS[:SEED_COUNT]

    return symbols[:SEED_COUNT]


def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:

    rows: List[Dict[str, Any]] = []

    for symbol in symbols:

        try:

            payload = load_runtime_asset(symbol)

            if isinstance(payload, dict):

                normalized = dict(payload)
                normalized["candles"] = _normalize_candles(
                    payload.get("candles", [])
                )

                rows.append(normalized)

        except Exception:
            continue

    return rows


def build_candle_cache(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:

    cache: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:

        symbol = str(row.get("asset") or row.get("symbol") or "")

        candles = row.get("candles", [])

        if symbol and candles:

            cache[symbol] = candles

    return cache


def build_candidate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    candidates: List[Dict[str, Any]] = []

    for row in rows:

        symbol = str(row.get("asset") or row.get("symbol") or "")

        candles = row.get("candles", [])

        if not symbol or len(candles) < 20:
            continue

        try:

            price = _to_float(row.get("price"))

            if price <= 0:
                continue

            vwap = compute_vwap_from_candles(candles, 20)

            if vwap <= 0:
                continue

            spread_bps = ((price - vwap) / vwap) * 10000

            buy_ok, reason = should_buy_mean_reversion(
                price,
                vwap,
                spread_bps,
                vwap_cfg,
            )

            candidate = dict(row)

            candidate.update(
                {
                    "asset": symbol,
                    "symbol": symbol,
                    "price": price,
                    "mid": price,
                    "vwap": vwap,
                    "spread_bps": abs(spread_bps),
                    "signal": "BUY" if buy_ok else "HOLD",
                    "reason": reason,
                    "candles": candles,
                }
            )

            candidates.append(candidate)

        except Exception:
            continue

    return candidates


def build_allocation_plan(
    ranked: List[Dict[str, Any]],
    total_capital: float
) -> List[Dict[str, Any]]:

    tradeable = [
        row for row in ranked if str(row.get("decision")) == "TRADE"
    ][:3]

    if not tradeable:
        return []

    total_score = sum(_to_float(row.get("score")) for row in tradeable)

    if total_score <= 0:
        equal_alloc = total_capital / len(tradeable)

        return [
            {"symbol": row["symbol"], "capital": equal_alloc}
            for row in tradeable
        ]

    plan = []

    for row in tradeable:

        score = _to_float(row.get("score"))

        capital_alloc = total_capital * (score / total_score)

        plan.append(
            {
                "symbol": row["symbol"],
                "capital": round(capital_alloc, 2),
            }
        )

    return plan


print("[CSS] Starting live dashboard...", flush=True)

while True:

    cycle += 1

    try:

        symbols = discover_coinbase_symbols()

        raw_rows = fetch_assets(symbols)

        candle_cache = build_candle_cache(raw_rows)

        candidate_rows = build_candidate_rows(raw_rows)

        feature_rows = feature_builder.enrich_rows(
            candidate_rows,
            candle_cache,
        )

        pressure_rows = pressure_engine.enrich_rows(feature_rows)

        ranked = ai.rank_opportunities(pressure_rows)

        ranked = pressure_trigger.apply(
            ranked,
            pressure_rows,
        )

        allocation_plan = build_allocation_plan(ranked, capital)

        _clear()

        print("==========================================================")
        print("     CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
        print("==========================================================")

        print(
            f"Cycle: {cycle} | Capital: ${capital:.2f} | Refresh: {SCAN_INTERVAL}s"
        )

        print("Configured Base Assets:", ", ".join(BASE_ASSETS))

        print("Active Symbols:", ", ".join(symbols))

        print("Timestamp (UTC):", now_utc())

        print("\nLIVE WATCHLIST")
        print("----------------------------------------------------------")

        if not candidate_rows:
            print("No watchlist rows built.")

        else:

            for row in candidate_rows[:MAX_DISPLAY]:

                print(
                    f"{row['symbol']:10}"
                    f"{row['mid']:10.4f}"
                    f"{row['vwap']:10.4f}"
                    f"{row['spread_bps']:10.2f}"
                    f"{row['signal']:>6}"
                )

        print("\nAI OPPORTUNITY SCANNER")
        print("----------------------------------------------------------")

        if not ranked:

            print("No ranked opportunities.")

        else:

            for row in ranked[:MAX_DISPLAY]:

                print(
                    f"{row['symbol']:10}"
                    f" score={row.get('score',0):.2f}"
                    f" pressure={row.get('pressure_score',0):.2f}"
                    f" decision={row.get('decision')}"
                )

        print("\nAI CAPITAL ALLOCATION PLAN")
        print("----------------------------------------------------------")

        if not allocation_plan:

            print("No allocations.")

        else:

            for item in allocation_plan:

                print(item)

        print(f"\nRefreshing in {SCAN_INTERVAL} seconds...")

        time.sleep(SCAN_INTERVAL)

    except KeyboardInterrupt:

        print("CSS stopped")

        break

    except Exception as exc:

        print("[CSS ERROR]", exc)

        time.sleep(SCAN_INTERVAL)