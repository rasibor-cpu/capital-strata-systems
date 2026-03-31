from __future__ import annotations

import multiprocessing as mp
import queue
import sys
import time
import traceback
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
from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager


FUTURES_SYMBOLS = {"ES", "NQ", "CL", "GC", "ZN"}
FUTURES_ENABLED = True


# =========================
# MODE CONTROL
# =========================

def choose_engine_mode() -> str:
    print("\n=== SELECT ENGINE MODE ===")
    print("1 SAFE")
    print("2 CONSERVATIVE")
    print("3 BALANCED")
    print("4 AGGRESSIVE")
    print("5 EXPANSION")

    try:
        choice = input("Select: ").strip()
    except Exception:
        choice = "3"

    return {
        "1": "SAFE",
        "2": "CONSERVATIVE",
        "3": "BALANCED",
        "4": "AGGRESSIVE",
        "5": "EXPANSION",
    }.get(choice, "BALANCED")


# =========================
# HELPERS
# =========================

def safe(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_asset(symbol: str) -> str:
    if symbol in FUTURES_SYMBOLS:
        return "FUTURES"
    if "_" in symbol:
        return "FX"
    if "-" in symbol:
        return "CRYPTO"
    return "OTHER"


def candle_value(candle: Any, field: str, default: float = 0.0) -> float:
    try:
        if isinstance(candle, dict):
            return safe(candle.get(field), default)
        return safe(getattr(candle, field, default), default)
    except Exception:
        return default


def normalize_candles(candles: List[Any]) -> List[Dict[str, float]]:
    normalized: List[Dict[str, float]] = []
    for candle in candles or []:
        normalized.append(
            {
                "open": candle_value(candle, "open"),
                "high": candle_value(candle, "high"),
                "low": candle_value(candle, "low"),
                "close": candle_value(candle, "close"),
                "volume": candle_value(candle, "volume"),
            }
        )
    return normalized


def compute_vwap_from_candles(candles: List[Any], fallback_price: float) -> float:
    total_pv = 0.0
    total_vol = 0.0

    for candle in candles[-50:]:
        high = candle_value(candle, "high")
        low = candle_value(candle, "low")
        close = candle_value(candle, "close")
        volume = candle_value(candle, "volume")

        typical = close
        if high > 0 and low > 0 and close > 0:
            typical = (high + low + close) / 3.0

        if typical > 0 and volume > 0:
            total_pv += typical * volume
            total_vol += volume

    if total_vol > 0:
        return total_pv / total_vol

    return fallback_price


def build_base_row(symbol: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = payload or {}
    candles = payload.get("candles") or []

    price = safe(payload.get("price"))
    if price <= 0 and candles:
        price = candle_value(candles[-1], "close", 0.0)

    prev_close = price
    if len(candles) >= 2:
        prev_close = candle_value(candles[-2], "close", price)

    momentum = 0.0
    if prev_close > 0:
        momentum = (price - prev_close) / (prev_close + 1e-9)

    vwap = safe(payload.get("vwap"))
    if vwap <= 0:
        vwap = compute_vwap_from_candles(candles, price)

    current_volume = safe(payload.get("volume"))
    if current_volume <= 0 and candles:
        current_volume = candle_value(candles[-1], "volume", 0.0)

    avg_volume = safe(payload.get("avg_volume"))
    if avg_volume <= 0 and candles:
        vols = [candle_value(c, "volume") for c in candles[-20:] if candle_value(c, "volume") > 0]
        if vols:
            avg_volume = sum(vols) / len(vols)

    return {
        **payload,
        "symbol": symbol,
        "asset": payload.get("asset") or symbol,
        "price": price,
        "current_price": safe(payload.get("current_price"), price),
        "vwap": vwap,
        "momentum": momentum,
        "velocity": momentum,
        "volume": current_volume,
        "avg_volume": avg_volume,
        "avg_volume_24h": safe(payload.get("avg_volume_24h"), avg_volume),
        "volume_24h": safe(payload.get("volume_24h"), current_volume),
        "volatility": safe(payload.get("volatility")),
        "price_compression": safe(payload.get("price_compression")),
        "compression": safe(payload.get("compression"), safe(payload.get("price_compression"))),
        "candles": candles,
    }


def normalize_signal_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    if "pressure_score" not in row:
        if "pressure" in row:
            row["pressure_score"] = safe(row.get("pressure"))
        elif "opportunity_pressure" in row:
            row["pressure_score"] = safe(row.get("opportunity_pressure"))
        else:
            row["pressure_score"] = 0.0

    if "confluence_score" not in row:
        if "confluence" in row:
            row["confluence_score"] = safe(row.get("confluence"))
        elif "signal_confluence" in row:
            row["confluence_score"] = safe(row.get("signal_confluence"))
        else:
            row["confluence_score"] = 0.0

    if "pressure_acceleration" not in row:
        if "accel" in row:
            row["pressure_acceleration"] = safe(row.get("accel"))
        elif "acceleration_score" in row:
            row["pressure_acceleration"] = safe(row.get("acceleration_score"))
        elif "acceleration" in row:
            row["pressure_acceleration"] = safe(row.get("acceleration"))
        else:
            row["pressure_acceleration"] = 0.0

    row["pressure"] = safe(row.get("pressure_score"))
    row["confluence"] = safe(row.get("confluence_score"))
    row["accel"] = safe(row.get("pressure_acceleration"))

    return row


def should_trade(row: Dict[str, Any], orch_score: float, mode_threshold: float) -> bool:
    pressure = safe(row.get("pressure_score"))
    confluence = safe(row.get("confluence_score"))
    accel = safe(row.get("pressure_acceleration"))

    pressure_ok = pressure >= 0.24
    confluence_ok = confluence >= 0.13
    momentum_ok = (accel > 0) or (pressure > 0.30)

    return (
        (pressure_ok and confluence_ok and momentum_ok)
        or (orch_score >= mode_threshold)
    )


# =========================
# PROCESS-BASED SCAN SUPPORT
# =========================

def _scan_worker(out_q: mp.Queue) -> None:
    try:
        local_scanner = UnifiedMarketScanner()
        result = local_scanner.scan() or []
        out_q.put(("ok", result))
    except Exception as e:
        out_q.put(("err", str(e)))


def timed_scan(timeout_seconds: int) -> List[Dict[str, Any]]:
    print(f"[STARTUP] scanner.scan() timeout={timeout_seconds}s")

    out_q: mp.Queue = mp.Queue()
    proc = mp.Process(target=_scan_worker, args=(out_q,), daemon=True)
    proc.start()
    proc.join(timeout_seconds)

    if proc.is_alive():
        proc.terminate()
        proc.join(2)
        print("[WARN] scanner timeout -> fallback")
        return []

    try:
        status, payload = out_q.get_nowait()
    except queue.Empty:
        print("[WARN] scanner returned no payload -> fallback")
        return []

    if status == "ok":
        print(f"[STARTUP] scan OK -> discovered={len(payload)}")
        return payload

    print(f"[WARN] scanner failed -> {payload}")
    return []


def resolve_symbols_from_discovery(
    discovered: List[Dict[str, Any]],
    limit: int,
    fallback_symbols: List[str],
) -> List[str]:
    symbols = list(
        {x["symbol"] for x in discovered if isinstance(x, dict) and x.get("symbol")}
    )[:limit]

    if symbols:
        return symbols

    fallback = fallback_symbols[:limit]
    print(f"[FALLBACK] using static symbols -> {fallback}")
    return fallback


# =========================
# MAIN APP
# =========================

def main() -> None:
    ENGINE_MODE = choose_engine_mode()

    MODE = {
        "SAFE": dict(symbols=5, refresh=15, trades=2, score=0.30, capital=5.0, fx=2, crypto=1, futures=1),
        "CONSERVATIVE": dict(symbols=7, refresh=12, trades=3, score=0.24, capital=7.0, fx=3, crypto=1, futures=1),
        "BALANCED": dict(symbols=10, refresh=10, trades=5, score=0.18, capital=10.0, fx=4, crypto=2, futures=1),
        "AGGRESSIVE": dict(symbols=12, refresh=8, trades=6, score=0.15, capital=12.0, fx=5, crypto=3, futures=2),
        "EXPANSION": dict(symbols=15, refresh=6, trades=8, score=0.12, capital=15.0, fx=6, crypto=4, futures=2),
    }[ENGINE_MODE]

    MAX_SYMBOLS_PER_CYCLE = int(MODE["symbols"])
    REFRESH_SECONDS = int(MODE["refresh"])
    MAX_TRADES_PER_CYCLE = int(MODE["trades"])
    BASE_TRADE_NOTIONAL_USD = float(MODE["capital"])
    MAX_OPEN_FX = int(MODE["fx"])
    MAX_OPEN_CRYPTO = int(MODE["crypto"])
    MAX_OPEN_FUTURES = int(MODE["futures"])
    SCAN_TIMEOUT_SECONDS = 20

    FALLBACK_SYMBOLS = [
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "XRP-USD",
        "ADA-USD",
        "DOGE-USD",
        "AVAX-USD",
        "LINK-USD",
        "LTC-USD",
        "BCH-USD",
        "ES",
        "NQ",
        "CL",
        "GC",
        "ZN",
    ]

    feature_builder = FeatureBuilder()
    regime_engine = MarketRegimeEngine()
    pressure_engine = OpportunityPressureEngine()
    accel_engine = PressureAccelerationEngine()
    confluence_engine = SignalConfluenceEngine()
    sweep_engine = LiquiditySweepDetector()

    ai = AIOpportunityScorer()
    optimizer = QuantSignalOptimizer()
    allocator = CapitalAllocator(total_capital=50.0, max_positions=5)
    orchestrator = TradeDecisionOrchestrator()

    position_manager = PositionManager()
    trade_logger = TradeLogger()

    futures_adapter = FuturesSimAdapter()
    futures_manager = FuturesPositionManager(futures_adapter)

    def get_open_counts() -> Dict[str, int]:
        counts = {"FX": 0, "CRYPTO": 0, "FUTURES": 0}
        try:
            open_positions = position_manager.get_open_positions()
            for s in open_positions:
                cls = classify_asset(str(s))
                if cls in counts:
                    counts[cls] += 1
        except Exception:
            pass

        try:
            futures_open = futures_manager.get_open_positions()
            counts["FUTURES"] = len(futures_open)
        except Exception:
            pass

        return counts

    def can_open(symbol: str) -> bool:
        counts = get_open_counts()
        cls = classify_asset(symbol)
        if cls == "FX":
            return counts["FX"] < MAX_OPEN_FX
        if cls == "CRYPTO":
            return counts["CRYPTO"] < MAX_OPEN_CRYPTO
        if cls == "FUTURES":
            return counts["FUTURES"] < MAX_OPEN_FUTURES
        return True

    print("[BOOT] CSS dashboard initializing")
    print(
        f"[BOOT] Mode={ENGINE_MODE} symbols={MAX_SYMBOLS_PER_CYCLE} "
        f"refresh={REFRESH_SECONDS}s trades={MAX_TRADES_PER_CYCLE} futures={FUTURES_ENABLED}"
    )

    cycle = 0
    equity = 200.0

    while True:
        cycle += 1

        try:
            print(f"\n[CYCLE] {cycle} starting")

            discovered = timed_scan(SCAN_TIMEOUT_SECONDS)
            symbols = resolve_symbols_from_discovery(
                discovered,
                MAX_SYMBOLS_PER_CYCLE,
                FALLBACK_SYMBOLS,
            )

            rows: List[Dict[str, Any]] = []
            for symbol in symbols:
                try:
                    raw = load_runtime_asset(symbol) or {}
                except Exception as e:
                    print(f"[LOAD-FAIL] {symbol} error={e}")
                    raw = {}

                if not raw:
                    continue

                candles = raw.get("candles") or []
                print(f"[LOAD] {symbol} candles={len(candles)}")
                rows.append(build_base_row(symbol, raw))

            print(f"[CYCLE] rows built={len(rows)}")
            if not rows:
                print("[CYCLE] no rows available; sleeping")
                time.sleep(REFRESH_SECONDS)
                continue

            print("[PIPELINE] feature_builder.enrich_rows")
            f = feature_builder.enrich_rows(rows, {})

            print("[PIPELINE] regime_engine.detect")
            r = regime_engine.detect(f)

            print("[PIPELINE] pressure_engine.enrich_rows")
            p = pressure_engine.enrich_rows(r)

            print("[PIPELINE] accel_engine.enrich_rows")
            a = accel_engine.enrich_rows(p)

            print("[PIPELINE] confluence_engine.enrich_rows")
            c = confluence_engine.enrich_rows(a)

            print("[PIPELINE] sweep_engine.enrich_rows")
            s_rows = sweep_engine.enrich_rows(c)

            s_rows = [normalize_signal_fields(dict(x)) for x in s_rows]

            print("[PIPELINE] ai.rank_opportunities")
            ranked = ai.rank_opportunities(s_rows)

            ranked = [normalize_signal_fields(dict(x)) for x in ranked]

            print("[PIPELINE] optimizer.optimize")
            optimized = optimizer.optimize(ranked)

            full_map: Dict[str, Dict[str, Any]] = {}
            for row in s_rows:
                sym = row.get("symbol")
                if sym:
                    full_map[sym] = dict(row)

            final_rows: List[Dict[str, Any]] = []
            for row in optimized:
                sym = row.get("symbol")
                if not sym:
                    continue

                merged = {**full_map.get(sym, {}), **row}
                merged = normalize_signal_fields(merged)

                normalized_candles = normalize_candles(merged.get("candles") or [])

                try:
                    orch = orchestrator.evaluate_trade(sym, normalized_candles)
                except Exception:
                    orch = {
                        "decision_score": 0.0,
                        "execute_trade": False,
                        "cost_decision": "ORCH_ERROR",
                        "net_edge_bps": 0.0,
                    }

                merged["decision_score"] = safe(orch.get("decision_score"))
                merged["execute_trade"] = bool(orch.get("execute_trade"))
                merged["cost_decision"] = orch.get("cost_decision", "NA")
                merged["net_edge_bps"] = safe(orch.get("net_edge_bps"))
                merged["orch"] = safe(orch.get("decision_score", 0.0))

                final_rows.append(merged)

            print(f"[PIPELINE] final_rows={len(final_rows)}")

            print("\n--- SIGNAL SNAPSHOT ---")
            for row in final_rows[:5]:
                print(
                    row["symbol"],
                    "pressure=", round(safe(row.get("pressure_score")), 3),
                    "accel=", round(safe(row.get("pressure_acceleration")), 3),
                    "conf=", round(safe(row.get("confluence_score")), 3),
                    "orch=", round(safe(row.get("decision_score", row.get("orch", 0.0))), 3),
                )

            ai_results = [
                {"symbol": row["symbol"], "opportunity_score": safe(row.get("score"))}
                for row in final_rows
            ]
            allocations = allocator.allocate(ai_results, final_rows)
            alloc_map = {a["symbol"]: a for a in allocations} if allocations else {}

            opened = 0
            for row in final_rows:
                if opened >= MAX_TRADES_PER_CYCLE:
                    break

                sym = row["symbol"]
                price = safe(row.get("price"))
                orch_score = safe(row.get("decision_score", row.get("orch", 0.0)))

                if price <= 0:
                    continue
                if not can_open(sym):
                    continue
                if not should_trade(row, orch_score, MODE["score"]):
                    continue

                capital = safe(
                    alloc_map.get(sym, {}).get("capital"),
                    BASE_TRADE_NOTIONAL_USD,
                )
                qty = capital / price
                if qty <= 0:
                    continue

                if classify_asset(sym) == "FUTURES" and FUTURES_ENABLED:
                    futures_result = futures_manager.open_position(
                        symbol=sym,
                        entry_price=price,
                        stop_price=price * 0.99,
                        contracts=1,
                        current_equity=equity,
                        state=row,
                    )

                    if futures_result.get("status") in {"OPENED", "APPROVED"}:
                        print(f"[FUTURES OPEN] {sym} score={orch_score:.3f} mode={ENGINE_MODE}")
                        opened += 1
                    else:
                        print(f"[FUTURES SKIP] {sym} -> {futures_result}")
                    continue

                try:
                    if position_manager.has_open_position(sym):
                        continue
                except Exception:
                    pass

                position_manager.open_long_position(
                    symbol=sym,
                    quantity=qty,
                    entry_price=price,
                    cycle_no=cycle,
                    opened_at_utc=now(),
                    asset_class=classify_asset(sym),
                    regime=str(row.get("regime", "NEUTRAL")).upper(),
                    pressure_score=safe(row.get("pressure_score")),
                    acceleration_score=safe(row.get("pressure_acceleration")),
                    signal_tier=str(row.get("signal_tier", "QUALIFIED")).upper(),
                    vwap=row.get("vwap"),
                    momentum=safe(row.get("momentum")),
                    velocity=safe(row.get("velocity")),
                    mean_reversion_score=safe(row.get("mean_reversion_score")),
                )

                try:
                    trade_logger.log_open(
                        symbol=sym,
                        entry_price=price,
                        quantity=qty,
                        score=safe(row.get("score")),
                        signal=f"MODE_{ENGINE_MODE}",
                        regime=row.get("regime", "NA"),
                        vwap=row.get("vwap", 0),
                        spread_pct=0,
                        momentum=row.get("momentum", 0),
                        velocity=row.get("velocity", 0),
                        vwap_dev=row.get("vwap_dev", 0),
                        mean_reversion_score=row.get("mean_reversion_score", 0),
                        pressure_score=row.get("pressure_score", 0),
                        acceleration_score=row.get("pressure_acceleration", 0),
                    )
                except Exception:
                    pass

                print(f"[OPEN] {sym} score={orch_score:.3f} mode={ENGINE_MODE}")
                opened += 1

            latest_prices: Dict[str, float] = {}
            intel_map: Dict[str, Dict[str, Any]] = {}

            for row in final_rows:
                sym = row["symbol"]
                latest_prices[sym] = safe(row.get("price"))
                intel_map[sym] = {
                    "vwap": row.get("vwap"),
                    "momentum": row.get("momentum"),
                    "velocity": row.get("velocity"),
                    "mean_reversion_score": row.get("mean_reversion_score"),
                }

            closed_trades = position_manager.update_positions(
                latest_prices=latest_prices,
                cycle_no=cycle,
                now=now(),
                intelligence_by_symbol=intel_map,
            )

            for trade in closed_trades:
                print(
                    f"[CLOSE] {trade['symbol']} "
                    f"reason={trade['exit_reason']} "
                    f"pnl={round(safe(trade.get('net_realized_pnl_pct')) * 100, 2)}%"
                )

            summary = position_manager.summary()
            equity = 200.0 + safe(summary.get("net_realized_pnl_usd"))

            futures_open_count = 0
            try:
                futures_open_count = len(futures_manager.get_open_positions())
            except Exception:
                pass

            print("===== CSS DASHBOARD =====")
            print(
                "Cycle:", cycle,
                "| Equity:", round(equity, 2),
                "| Open:", summary.get("open_positions_count", 0),
                "| Futures Open:", futures_open_count,
                "| Closed:", summary.get("closed_positions_count", 0),
                "| Mode:", ENGINE_MODE,
            )

            time.sleep(REFRESH_SECONDS)

        except KeyboardInterrupt:
            print("\n[STOP] CSS dashboard interrupted by user")
            break
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    mp.freeze_support()
    main()