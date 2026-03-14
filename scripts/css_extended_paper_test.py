from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import (
    Candle,
    load_runtime_asset,
    compute_vwap_from_candles,
)
from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer

SCAN_INTERVAL_SECONDS = 12
SEED_COUNT = 40
MAX_OPEN_POSITIONS = 8

STARTING_CAPITAL = 200.0

TAKE_PROFIT_PCT = 0.009
STOP_LOSS_PCT = 0.008
MAX_HOLD_CYCLES = 12

MIN_TRADE_SCORE = 0.22
MIN_PRESSURE_SCORE = 0.06
MIN_PRESSURE_ACCEL = 0.00

scanner = UnifiedMarketScanner()
feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()

open_positions: Dict[str, Dict[str, Any]] = {}


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def infer_direction(price: float, vwap: float) -> str:
    if price < vwap:
        return "LONG"
    return "SHORT"


def candle_to_dict(c: Candle) -> Dict[str, float]:
    return {
        "ts": float(c.ts),
        "open": float(c.open),
        "high": float(c.high),
        "low": float(c.low),
        "close": float(c.close),
        "volume": float(c.volume),
    }


def discover_symbols() -> List[str]:
    results = scanner.scan()

    symbols: List[str] = []
    seen = set()

    for r in results:
        if r.get("venue") != "COINBASE":
            continue

        s = r.get("symbol")
        if not s or s in seen:
            continue

        seen.add(s)
        symbols.append(s)

    return symbols[:SEED_COUNT]


def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for s in symbols:
        try:
            payload = load_runtime_asset(s)
            candles_raw: List[Candle] = payload.get("candles", [])

            if len(candles_raw) < 10:
                continue

            raw_price = payload.get("price")
            price = float(candles_raw[-1].close) if raw_price is None else float(raw_price)
            if price <= 0:
                continue

            vwap = compute_vwap_from_candles(candles_raw)
            if not vwap or vwap <= 0:
                continue

            candles = [candle_to_dict(c) for c in candles_raw]

            row = dict(payload)
            row["symbol"] = s
            row["price"] = float(price)
            row["vwap"] = float(vwap)
            row["candles"] = candles

            direction = infer_direction(float(price), float(vwap))
            row["direction"] = direction
            row["side"] = direction
            row["signal_direction"] = direction

            rows.append(row)

        except Exception as e:
            print("[FETCH ERROR]", s, e)

    return rows


def enrich_pressure_features(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for r in rows:
        candles = r.get("candles", [])
        price = _safe_float(r.get("price"))
        vwap = _safe_float(r.get("vwap"))

        if not candles or price <= 0 or vwap <= 0:
            r["pressure_score"] = 0.0
            r["pressure_acceleration"] = 0.0
            continue

        last_volume = _safe_float(candles[-1].get("volume"))
        recent_block = candles[-20:] if len(candles) >= 20 else candles
        avg_volume = (
            sum(_safe_float(c.get("volume")) for c in recent_block) / max(1, len(recent_block))
        )

        vwap_distance = abs(price - vwap) / vwap if vwap > 0 else 0.0

        recent_ranges = []
        for c in candles[-6:]:
            high = _safe_float(c.get("high"))
            low = _safe_float(c.get("low"))
            close = _safe_float(c.get("close"))
            if close > 0:
                recent_ranges.append((high - low) / close)

        avg_recent_range = sum(recent_ranges) / len(recent_ranges) if recent_ranges else 0.0

        closes = [_safe_float(c.get("close")) for c in candles[-6:]]
        momentum = 0.0
        if len(closes) >= 2 and closes[0] > 0:
            momentum = abs((closes[-1] - closes[0]) / closes[0])

        volume_ratio = (last_volume / avg_volume) if avg_volume > 0 else 0.0

        pressure_score = (
            min(vwap_distance * 8.0, 0.35)
            + min(volume_ratio / 3.0, 0.25)
            + min(avg_recent_range * 6.0, 0.20)
            + min(momentum * 5.0, 0.20)
        )

        older_ranges = []
        for c in candles[-12:-6]:
            high = _safe_float(c.get("high"))
            low = _safe_float(c.get("low"))
            close = _safe_float(c.get("close"))
            if close > 0:
                older_ranges.append((high - low) / close)

        avg_older_range = sum(older_ranges) / len(older_ranges) if older_ranges else 0.0
        pressure_accel = max(0.0, avg_recent_range - avg_older_range)

        r["pressure_score"] = round(pressure_score, 4)
        r["pressure_acceleration"] = round(pressure_accel, 4)

    return rows


def enforce_direction(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for r in rows:
        price = _safe_float(r.get("price"))
        vwap = _safe_float(r.get("vwap"))
        direction = infer_direction(price, vwap) if price > 0 and vwap > 0 else "LONG"

        r["direction"] = direction
        r["side"] = direction
        r["signal_direction"] = direction

    return rows


def build_signals(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = feature_builder.enrich_rows(rows, {})
    rows = regime_engine.detect(rows)

    # First injection before scoring
    rows = enforce_direction(rows)
    rows = enrich_pressure_features(rows)

    rows = ai.rank_opportunities(rows)
    rows = optimizer.optimize(rows)

    # Critical repair: re-inject after scoring/optimizer layers
    rows = enforce_direction(rows)
    rows = enrich_pressure_features(rows)

    rows.sort(key=lambda x: _safe_float(x.get("trade_score")), reverse=True)
    return rows


def allow_trade(row: Dict[str, Any]) -> bool:
    decision = str(row.get("decision", "")).upper()
    trade_score = _safe_float(row.get("trade_score"))
    pressure = _safe_float(row.get("pressure_score"))
    accel = _safe_float(row.get("pressure_acceleration"))

    if decision == "TRADE" and trade_score >= MIN_TRADE_SCORE:
        return True

    if trade_score >= MIN_TRADE_SCORE and pressure >= MIN_PRESSURE_SCORE:
        return True

    if pressure >= 0.12 and accel >= MIN_PRESSURE_ACCEL:
        return True

    return False


def open_positions_if_allowed(rows: List[Dict[str, Any]]) -> None:
    available = MAX_OPEN_POSITIONS - len(open_positions)
    if available <= 0:
        return

    for r in rows:
        if not allow_trade(r):
            continue

        symbol = r["symbol"]
        if symbol in open_positions:
            continue

        entry = float(r["price"])
        size = STARTING_CAPITAL / MAX_OPEN_POSITIONS

        open_positions[symbol] = {
            "entry": entry,
            "size": size,
            "cycles": 0,
        }

        print(
            "OPEN:",
            symbol,
            "score=",
            round(_safe_float(r.get("trade_score")), 4),
            "pressure=",
            round(_safe_float(r.get("pressure_score")), 4),
            "accel=",
            round(_safe_float(r.get("pressure_acceleration")), 4),
        )

        if len(open_positions) >= MAX_OPEN_POSITIONS:
            break


print("CSS EXTENDED PAPER TEST STARTED")

while True:
    try:
        symbols = discover_symbols()
        rows = fetch_assets(symbols)

        print("VALID ASSETS AFTER FILTER:", len(rows))

        if rows:
            signals = build_signals(rows)

            print("\n--- TOP SIGNALS ---")
            for r in signals[:10]:
                print(
                    r.get("symbol"),
                    "decision=",
                    r.get("decision"),
                    "direction=",
                    r.get("direction"),
                    "score=",
                    round(_safe_float(r.get("trade_score")), 4),
                    "pressure=",
                    round(_safe_float(r.get("pressure_score")), 4),
                    "accel=",
                    round(_safe_float(r.get("pressure_acceleration")), 4),
                )
            print("-------------------\n")

            open_positions_if_allowed(signals)

        time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("Stopped.")
        break

    except Exception as e:
        print("ENGINE ERROR:", e)
        traceback.print_exc()
        time.sleep(5)