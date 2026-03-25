# CSS DASHBOARD — FULL NON-REGRESSION + DATA-FED PRESSURE/ACCEL FIX

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
from backend.execution.position_manager import PositionManager
from backend.execution.trade_logger import TradeLogger
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.liquidity_sweep_detector import LiquiditySweepDetector
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

# ---------------- CONFIG ----------------

MAX_SYMBOLS_PER_CYCLE = 10
REFRESH_SECONDS = 10
MAX_TRADES_PER_CYCLE = 5

MAX_OPEN_FX = 4
MAX_OPEN_CRYPTO = 2
MAX_OPEN_FUTURES = 2

BASE_TRADE_NOTIONAL_USD = 10.0

# ---------------- ENGINES ----------------

scanner = UnifiedMarketScanner()
feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
confluence_engine = SignalConfluenceEngine()
sweep_engine = LiquiditySweepDetector()

ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()
allocator = CapitalAllocator(total_capital=50.0, max_positions=5)

position_manager = PositionManager()
trade_logger = TradeLogger()

GLOBAL_CONTEXT: Dict[str, Dict[str, Any]] = {}

# ---------------- HELPERS ----------------

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")

def safe(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d

def clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v

def classify_asset(symbol: str) -> str:
    if "_" in symbol:
        return "FX"
    if "-" in symbol:
        return "CRYPTO"
    return "OTHER"

def get_open_counts() -> Dict[str, int]:
    counts = {"FX": 0, "CRYPTO": 0, "FUTURES": 0}
    for s in position_manager.get_open_positions():
        cls = classify_asset(s)
        if cls in counts:
            counts[cls] += 1
    return counts

def can_open(symbol: str) -> bool:
    counts = get_open_counts()
    cls = classify_asset(symbol)
    if cls == "FX":
        return counts["FX"] < MAX_OPEN_FX
    if cls == "CRYPTO":
        return counts["CRYPTO"] < MAX_OPEN_CRYPTO
    return True

def extract_candles(payload: Dict[str, Any]) -> List[Any]:
    candidates = [
        payload.get("candles"),
        payload.get("ohlcv"),
        payload.get("bars"),
        payload.get("history"),
        payload.get("data"),
    ]
    for item in candidates:
        if isinstance(item, list) and item:
            return item
    return []

def candle_attr(candle: Any, name: str, default: float = 0.0) -> float:
    try:
        if isinstance(candle, dict):
            return safe(candle.get(name), default)

        if hasattr(candle, name):
            return safe(getattr(candle, name), default)

        if isinstance(candle, (list, tuple)):
            idx_map = {
                "ts": 0,
                "open": 1,
                "high": 2,
                "low": 3,
                "close": 4,
                "volume": 5,
            }
            idx = idx_map.get(name)
            if idx is not None and len(candle) > idx:
                return safe(candle[idx], default)
    except Exception:
        return default
    return default

def compute_avg_volume_from_candles(candles: List[Any], window: int = 20) -> float:
    if not candles:
        return 0.0
    subset = candles[-window:] if len(candles) >= window else candles
    vols = [candle_attr(c, "volume") for c in subset if candle_attr(c, "volume") > 0]
    if not vols:
        return 0.0
    return sum(vols) / len(vols)

def compute_current_volume(candles: List[Any]) -> float:
    if not candles:
        return 0.0
    return candle_attr(candles[-1], "volume", 0.0)

def compute_volatility_from_candles(candles: List[Any], window: int = 20) -> float:
    if not candles:
        return 0.0
    subset = candles[-window:] if len(candles) >= window else candles
    rel_ranges: List[float] = []
    for c in subset:
        high = candle_attr(c, "high")
        low = candle_attr(c, "low")
        close = candle_attr(c, "close")
        if close > 0 and high >= low:
            rel_ranges.append((high - low) / close)
    if not rel_ranges:
        return 0.0
    return sum(rel_ranges) / len(rel_ranges)

def compute_price_compression_from_candles(candles: List[Any], window: int = 20) -> float:
    if len(candles) < 5:
        return 0.0

    subset = candles[-window:] if len(candles) >= window else candles
    closes = [candle_attr(c, "close") for c in subset if candle_attr(c, "close") > 0]
    highs = [candle_attr(c, "high") for c in subset]
    lows = [candle_attr(c, "low") for c in subset]

    if not closes or not highs or not lows:
        return 0.0

    price_ref = closes[-1]
    if price_ref <= 0:
        return 0.0

    total_range = max(highs) - min(lows)
    norm_range = total_range / price_ref

    if norm_range <= 0:
        return 1.0

    compression = 1.0 - min(norm_range / 0.08, 1.0)
    return clamp01(compression)

def compute_metrics(symbol: str, price: float, vwap: float) -> tuple[float, float, float, float]:
    prev = GLOBAL_CONTEXT.get(symbol, {})

    prev_price = prev.get("price", price)
    prev_momentum = prev.get("momentum", 0.0)

    momentum = (price - prev_price) / (prev_price + 1e-9)
    velocity = momentum - prev_momentum

    if vwap == 0:
        vwap = price * 0.999 if price > 0 else 1.0

    vwap_dev = (price - vwap) / (vwap + 1e-9)
    if vwap_dev == 0:
        vwap_dev = 0.001 if price >= vwap else -0.001

    mean_rev = abs(vwap_dev) * 2.0
    if abs(momentum) < 0.003:
        mean_rev += 0.2
    if velocity < 0:
        mean_rev += 0.2

    GLOBAL_CONTEXT[symbol] = {
        "price": price,
        "momentum": momentum,
    }

    return momentum, velocity, vwap_dev, min(mean_rev, 1.0)

def build_runtime_row(sym: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    candles = extract_candles(payload)

    price = safe(payload.get("price"))
    if price <= 0 and candles:
        price = candle_attr(candles[-1], "close", 0.0)

    vwap = safe(payload.get("vwap"))
    if vwap <= 0 and price > 0:
        vwap = price * 0.999

    momentum, velocity, vwap_dev, mean_rev = compute_metrics(sym, price, vwap)

    current_volume = safe(payload.get("volume"))
    if current_volume <= 0:
        current_volume = compute_current_volume(candles)

    avg_volume = safe(payload.get("avg_volume"))
    if avg_volume <= 0:
        avg_volume = compute_avg_volume_from_candles(candles, window=20)

    volatility = safe(payload.get("volatility"))
    if volatility <= 0:
        volatility = compute_volatility_from_candles(candles, window=20)

    price_compression = safe(payload.get("price_compression"))
    if price_compression <= 0:
        price_compression = compute_price_compression_from_candles(candles, window=20)

    row: Dict[str, Any] = {
        "symbol": sym,
        "price": price,
        "current_price": price,
        "vwap": vwap,
        "candles": candles,
        "volume": current_volume,
        "avg_volume": avg_volume,
        "avg_volume_24h": avg_volume,
        "volume_24h": max(current_volume, avg_volume),
        "volatility": volatility,
        "avg_volatility": volatility if volatility > 0 else 0.01,
        "price_compression": price_compression,
        "compression": price_compression,
        "momentum": momentum,
        "velocity": velocity,
        "trend_efficiency": min(abs(momentum) * 8.0, 1.0),
        "vwap_dev": vwap_dev,
        "vwap_distance": vwap_dev,
        "mean_reversion_score": mean_rev,
        "spread_bps": safe(payload.get("spread_bps"), 2.0),
        "slippage_bps": safe(payload.get("slippage_bps"), 3.0),
        "top_of_book_depth": safe(payload.get("top_of_book_depth"), 100000.0),
        "order_flow_delta": 0.0,
        "buy_pressure": max(momentum, 0.0),
        "sell_pressure": max(-momentum, 0.0),
        "recent_high": max([candle_attr(c, "high") for c in candles[-20:]], default=price),
        "recent_low": min(
            [candle_attr(c, "low") for c in candles[-20:] if candle_attr(c, "low") > 0],
            default=price,
        ),
        "rejection_strength": 0.0,
        "wick_reversal_strength": 0.0,
        "liquidity_sweep_flag": False,
    }

    return row

# ---------------- MAIN ----------------

cycle = 0
equity = 200.0

while True:
    cycle += 1

    try:
        discovered = scanner.scan()
        symbols = list({x["symbol"] for x in discovered})[:MAX_SYMBOLS_PER_CYCLE]

        rows: List[Dict[str, Any]] = []

        for sym in symbols:
            payload = load_runtime_asset(sym)
            rows.append(build_runtime_row(sym, payload))

        if not rows:
            time.sleep(REFRESH_SECONDS)
            continue

        # FULL PIPELINE
        f = feature_builder.enrich_rows(rows, {})
        r = regime_engine.detect(f)
        p = pressure_engine.enrich_rows(r)
        a = accel_engine.enrich_rows(p)
        c = confluence_engine.enrich_rows(a)
        s = sweep_engine.enrich_rows(c)

        ranked = ai.rank_opportunities(s)
        optimized = optimizer.optimize(ranked)

        # REATTACH FULL METRICS
        base_map = {row["symbol"]: row for row in s}
        final_rows: List[Dict[str, Any]] = []

        for row in optimized:
            sym = row["symbol"]
            base = base_map.get(sym, {})
            merged = {**base, **row}

            if safe(merged.get("momentum")) == 0.0:
                merged["momentum"] = base.get("momentum", 0.001)

            if safe(merged.get("velocity")) == 0.0:
                merged["velocity"] = base.get("velocity", 0.0005)

            if safe(merged.get("mean_reversion_score")) == 0.0:
                merged["mean_reversion_score"] = base.get("mean_reversion_score", 0.2)

            if safe(merged.get("pressure_score")) == 0.0:
                merged["pressure_score"] = max(abs(safe(merged.get("vwap_dev"))), 0.01)

            if safe(merged.get("pressure_acceleration")) == 0.0:
                merged["pressure_acceleration"] = merged.get("velocity", 0.0005)

            if safe(merged.get("acceleration_score")) == 0.0:
                merged["acceleration_score"] = abs(safe(merged.get("pressure_acceleration")))

            final_rows.append(merged)

        final_rows.sort(key=lambda x: safe(x.get("score")), reverse=True)

        # ALLOCATION
        ai_results = [
            {"symbol": x["symbol"], "opportunity_score": x.get("score", 0)}
            for x in final_rows
        ]
        allocations = allocator.allocate(ai_results, final_rows)

        if not allocations:
            allocations = [
                {"symbol": x["symbol"], "capital": BASE_TRADE_NOTIONAL_USD}
                for x in final_rows[:3]
            ]

        alloc_map = {a["symbol"]: a for a in allocations}

        opened = 0

        # ---------------- PROFITABILITY FILTER ----------------

        for row in final_rows:
            if opened >= MAX_TRADES_PER_CYCLE:
                break

            sym = row["symbol"]
            price = safe(row.get("price"))

            if price <= 0:
                continue

            if not can_open(sym):
                continue

            score = safe(row.get("score"))
            mr = safe(row.get("mean_reversion_score"))
            pressure_score = safe(row.get("pressure_score"))
            accel_score = safe(row.get("pressure_acceleration"))
            momentum_abs = abs(safe(row.get("momentum")))

            if mr < 0.25:
                continue
            if pressure_score < 0.10:
                continue
            if momentum_abs < 0.0003:
                continue
            if abs(accel_score) < 0.0001:
                continue
            if score < 0.18:
                continue

            alloc = alloc_map.get(sym, {})
            capital = safe(alloc.get("capital"), BASE_TRADE_NOTIONAL_USD)

            qty = capital / price
            if qty <= 0:
                continue

            position_manager.open_long_position(
                symbol=sym,
                quantity=qty,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now(),
            )

            trade_logger.log_open(
                symbol=sym,
                entry_price=price,
                quantity=qty,
                score=score,
                signal="QUALIFIED",
                regime=row.get("regime", "NA"),
                vwap=row.get("vwap", 0),
                spread_pct=0,
                momentum=row.get("momentum", 0),
                velocity=row.get("velocity", 0),
                vwap_dev=row.get("vwap_dev", 0),
                mean_reversion_score=mr,
                pressure_score=pressure_score,
                acceleration_score=accel_score,
            )

            print(f"[OPEN] {sym} score={score:.3f} mr={mr:.3f} p={pressure_score:.3f} a={accel_score:.5f}")
            opened += 1

        closed = position_manager.update_positions(
            {x["symbol"]: x["price"] for x in rows},
            cycle,
            now(),
        )

        for trade in closed:
            pnl = safe(trade.get("realized_pnl_usd"))
            equity += pnl

            trade_logger.log_close(
                symbol=trade["symbol"],
                entry_price=trade["entry_price"],
                exit_price=trade["exit_price"],
                quantity=trade["quantity"],
                reason=trade.get("exit_reason", "UNKNOWN"),
                hold_minutes=trade.get("cycles_held", 0),
            )

            print("[CLOSE]", trade["symbol"], pnl)

        clear()

        counts = get_open_counts()

        print("===== CSS DASHBOARD =====")
        print("Cycle:", cycle, "Equity:", round(equity, 2))
        print("Open:", counts)

        print("\nAllocator:")
        for a in allocations:
            print(a["symbol"], a["capital"])

        print("\nTop:")
        for r in final_rows[:10]:
            print(
                r["symbol"],
                "score", round(safe(r.get("score")), 3),
                "m", round(safe(r.get("momentum")), 5),
                "v", round(safe(r.get("velocity")), 5),
                "mr", round(safe(r.get("mean_reversion_score")), 3),
                "p", round(safe(r.get("pressure_score")), 3),
                "a", round(safe(r.get("pressure_acceleration")), 5),
                "vol", round(safe(r.get("volatility")), 5),
                "cmp", round(safe(r.get("price_compression")), 3),
            )

        time.sleep(REFRESH_SECONDS)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(REFRESH_SECONDS)