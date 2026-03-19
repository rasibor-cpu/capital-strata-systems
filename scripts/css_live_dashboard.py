from __future__ import annotations

import json
import os
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
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.liquidity_sweep_detector import LiquiditySweepDetector
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.intelligence.vwap_elasticity_engine import VWAPElasticityEngine
from backend.scanner.spread_normalizer import normalize_snapshot_spread
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)

SUMMARY_FILE = ARTIFACT_DIR / "css_extended_paper_test_summary.json"
POSITIONS_FILE = ARTIFACT_DIR / "css_open_positions.json"
CLOSED_TRADES_FILE = ARTIFACT_DIR / "css_closed_trades.json"

MAX_SYMBOLS_PER_CYCLE = 25
MAX_TRADES_PER_CYCLE = 5
REFRESH_SECONDS = 10

ENGINE_PROFILES: Dict[str, Dict[str, float]] = {
    "safe/test": {
        "min_confluence_to_reach_optimizer": 0.90,
        "min_pressure_to_reach_optimizer": 0.30,
        "min_accel_to_reach_optimizer": 0.15,
        "min_abs_spread_bps_to_reach_optimizer": 20.0,
        "min_trade_score_to_execute": 0.66,
        "min_confluence_to_execute": 0.90,
        "min_pressure_to_execute": 0.30,
        "min_accel_or_pressure_boost": 0.15,
        "min_vwap_dev_abs_to_execute": 0.018,
        "min_reversion_window_score": 0.72,
        "min_elasticity_score": 0.35,
    },
    "conservative": {
        "min_confluence_to_reach_optimizer": 0.84,
        "min_pressure_to_reach_optimizer": 0.24,
        "min_accel_to_reach_optimizer": 0.10,
        "min_abs_spread_bps_to_reach_optimizer": 16.0,
        "min_trade_score_to_execute": 0.60,
        "min_confluence_to_execute": 0.84,
        "min_pressure_to_execute": 0.24,
        "min_accel_or_pressure_boost": 0.10,
        "min_vwap_dev_abs_to_execute": 0.015,
        "min_reversion_window_score": 0.64,
        "min_elasticity_score": 0.30,
    },
    "balanced": {
        "min_confluence_to_reach_optimizer": 0.80,
        "min_pressure_to_reach_optimizer": 0.22,
        "min_accel_to_reach_optimizer": 0.09,
        "min_abs_spread_bps_to_reach_optimizer": 14.0,
        "min_trade_score_to_execute": 0.62,
        "min_confluence_to_execute": 0.80,
        "min_pressure_to_execute": 0.22,
        "min_accel_or_pressure_boost": 0.09,
        "min_vwap_dev_abs_to_execute": 0.018,
        "min_reversion_window_score": 0.60,
        "min_elasticity_score": 0.32,
    },
    "aggressive": {
        "min_confluence_to_reach_optimizer": 0.70,
        "min_pressure_to_reach_optimizer": 0.16,
        "min_accel_to_reach_optimizer": 0.06,
        "min_abs_spread_bps_to_reach_optimizer": 10.0,
        "min_trade_score_to_execute": 0.50,
        "min_confluence_to_execute": 0.70,
        "min_pressure_to_execute": 0.16,
        "min_accel_or_pressure_boost": 0.06,
        "min_vwap_dev_abs_to_execute": 0.010,
        "min_reversion_window_score": 0.48,
        "min_elasticity_score": 0.20,
    },
    "opportunistic/expansion": {
        "min_confluence_to_reach_optimizer": 0.62,
        "min_pressure_to_reach_optimizer": 0.12,
        "min_accel_to_reach_optimizer": 0.04,
        "min_abs_spread_bps_to_reach_optimizer": 8.0,
        "min_trade_score_to_execute": 0.44,
        "min_confluence_to_execute": 0.62,
        "min_pressure_to_execute": 0.12,
        "min_accel_or_pressure_boost": 0.04,
        "min_vwap_dev_abs_to_execute": 0.008,
        "min_reversion_window_score": 0.42,
        "min_elasticity_score": 0.16,
    },
}

ALLOWED_EXECUTION_REGIMES = {
    "MEAN_REVERSION",
    "TREND",
    "VOLATILE",
    "BREAKOUT",
    "NEUTRAL",
    "RANGE",
}

scanner = UnifiedMarketScanner()

feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
confluence_engine = SignalConfluenceEngine()
elasticity_engine = VWAPElasticityEngine()
sweep_engine = LiquiditySweepDetector()
ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()

position_manager = PositionManager(
    take_profit_pct=0.018,
    stop_loss_pct=0.010,
    max_hold_cycles=5,
)

starting_capital = 200.0
estimated_equity = starting_capital
cycle = 0
_debug_payload_logged = False
_last_closed_trade: Dict[str, Any] | None = None


class VWAPDeviationEngine:
    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []
        for row in rows:
            price = safe_float(row.get("price"), 0.0)
            vwap = safe_float(row.get("vwap"), 0.0)

            new_row = dict(row)
            dev = (price - vwap) / vwap if vwap > 0.0 else 0.0
            new_row["vwap_dev"] = dev
            new_row["vwap_dev_abs"] = abs(dev)
            enriched.append(new_row)
        return enriched


class VWAPReversionWindowEngine:
    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            vwap_dev_abs = safe_float(row.get("vwap_dev_abs"), 0.0)
            pressure = safe_float(row.get("pressure_score"), 0.0)
            accel = safe_float(row.get("pressure_acceleration"), 0.0)
            confluence = safe_float(row.get("confluence_score"), 0.0)
            elasticity_score = safe_float(row.get("elasticity_score"), 0.0)
            regime = str(row.get("regime", "NEUTRAL")).upper()

            deviation_fit = band_pass_score(
                value=vwap_dev_abs,
                lower=0.012,
                ideal_low=0.020,
                ideal_high=0.085,
                upper=0.140,
            )

            pressure_fit = clamp01(pressure / 0.40)
            accel_fit = clamp01(accel / 0.12)
            confluence_fit = clamp01(confluence / 0.90)

            regime_fit_map = {
                "MEAN_REVERSION": 1.00,
                "RANGE": 0.92,
                "NEUTRAL": 0.82,
                "VOLATILE": 0.76,
                "TREND": 0.70,
                "BREAKOUT": 0.64,
            }
            regime_fit = regime_fit_map.get(regime, 0.55)

            reversion_window_score = clamp01(
                0.32 * deviation_fit
                + 0.16 * pressure_fit
                + 0.08 * accel_fit
                + 0.20 * confluence_fit
                + 0.12 * regime_fit
                + 0.12 * elasticity_score
            )

            reversion_window_pass = (
                deviation_fit >= 0.45
                and confluence_fit >= 0.60
                and reversion_window_score >= 0.40
            )

            new_row = dict(row)
            new_row["reversion_window_score"] = reversion_window_score
            new_row["reversion_window_pass"] = reversion_window_pass
            enriched.append(new_row)

        return enriched


class EliteSignalClassifier:
    def classify(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        classified: List[Dict[str, Any]] = []

        for row in rows:
            confluence = safe_float(row.get("confluence_score"), 0.0)
            pressure = safe_float(row.get("pressure_score"), 0.0)
            vwap_dev_abs = safe_float(row.get("vwap_dev_abs"), 0.0)
            trade_score = safe_float(row.get("trade_score"), 0.0)
            reversion_window_score = safe_float(row.get("reversion_window_score"), 0.0)
            elasticity_score = safe_float(row.get("elasticity_score"), 0.0)

            tier = "WATCH"
            decision = "WATCH"

            if trade_score >= 0.45 and reversion_window_score >= 0.40:
                tier = "QUALIFIED"
                decision = "TRADE"

            if (
                confluence >= 0.88
                and pressure >= 0.30
                and vwap_dev_abs >= 0.015
                and trade_score >= 0.55
                and reversion_window_score >= 0.62
                and elasticity_score >= 0.35
            ):
                tier = "ELITE"
                decision = "TRADE"

            new_row = dict(row)
            new_row["signal_tier"] = tier
            new_row["decision"] = decision
            classified.append(new_row)

        return classified


vwap_engine = VWAPDeviationEngine()
reversion_window_engine = VWAPReversionWindowEngine()
elite_classifier = EliteSignalClassifier()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def band_pass_score(
    *,
    value: float,
    lower: float,
    ideal_low: float,
    ideal_high: float,
    upper: float,
) -> float:
    if value <= lower or value >= upper:
        return 0.0
    if ideal_low <= value <= ideal_high:
        return 1.0
    if value < ideal_low:
        span = ideal_low - lower
        return clamp01((value - lower) / span) if span > 0 else 0.0
    span = upper - ideal_high
    return clamp01((upper - value) / span) if span > 0 else 0.0


def candle_attr(candle: Any, name: str, default: float = 0.0) -> float:
    if hasattr(candle, name):
        return safe_float(getattr(candle, name), default)

    if isinstance(candle, dict):
        return safe_float(candle.get(name, default), default)

    if isinstance(candle, (list, tuple)):
        idx_map = {"ts": 0, "open": 1, "high": 2, "low": 3, "close": 4, "volume": 5}
        idx = idx_map.get(name)
        if idx is not None and len(candle) > idx:
            return safe_float(candle[idx], default)

    return float(default)


def normalize_candle(candle: Any) -> Dict[str, float]:
    return {
        "ts": candle_attr(candle, "ts", 0.0),
        "open": candle_attr(candle, "open", 0.0),
        "high": candle_attr(candle, "high", 0.0),
        "low": candle_attr(candle, "low", 0.0),
        "close": candle_attr(candle, "close", 0.0),
        "volume": candle_attr(candle, "volume", 0.0),
    }


def normalize_candles(candles: List[Any]) -> List[Dict[str, float]]:
    return [normalize_candle(c) for c in candles]


def choose_engine_mode() -> str:
    print("\nSelect CSS Engine Mode for this session:\n")
    print("1. safe/test")
    print("2. conservative")
    print("3. balanced")
    print("4. aggressive")
    print("5. opportunistic/expansion\n")

    choice = input("Enter choice (1-5): ").strip()

    mapping = {
        "1": "safe/test",
        "2": "conservative",
        "3": "balanced",
        "4": "aggressive",
        "5": "opportunistic/expansion",
    }

    mode = mapping.get(choice, "balanced")
    print(f"\n[CSS] Engine mode locked for this session: {mode.upper()}\n")
    return mode


def regime_alignment_score(regime: str) -> float:
    r = str(regime).upper()
    if r == "MEAN_REVERSION":
        return 1.00
    if r == "TREND":
        return 0.90
    if r == "BREAKOUT":
        return 0.88
    if r == "VOLATILE":
        return 0.82
    if r in {"NEUTRAL", "RANGE"}:
        return 0.72
    return 0.40


def blended_conviction_score(
    *,
    base_ai_score: float,
    confluence_score: float,
    pressure_score: float,
    pressure_acceleration: float,
    regime: str,
    vwap_dev_abs: float,
    reversion_window_score: float,
    elasticity_score: float,
) -> float:
    regime_score = regime_alignment_score(regime)
    score = (
        0.11 * clamp01(base_ai_score)
        + 0.24 * clamp01(confluence_score)
        + 0.17 * clamp01(pressure_score)
        + 0.09 * clamp01(pressure_acceleration)
        + 0.08 * clamp01(regime_score)
        + 0.11 * clamp01(vwap_dev_abs * 25.0)
        + 0.12 * clamp01(reversion_window_score)
        + 0.08 * clamp01(elasticity_score)
    )
    return clamp01(score)


def call_rows_module(module: Any, rows: List[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    if hasattr(module, "enrich_rows"):
        return module.enrich_rows(rows)
    if hasattr(module, "enrich"):
        return module.enrich(rows)
    if hasattr(module, "detect"):
        return module.detect(rows)

    print(f"[PIPELINE-WARN] {label}: no compatible row method found, passing rows through")
    return rows


def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:
    global _debug_payload_logged

    rows: List[Dict[str, Any]] = []

    for symbol in symbols:
        try:
            payload = load_runtime_asset(symbol)

            if not isinstance(payload, dict):
                print(f"[ROW-SKIP] {symbol}: payload is not dict")
                continue

            payload = normalize_snapshot_spread(payload)

            raw_candles = payload.get("candles", [])
            if not isinstance(raw_candles, list) or len(raw_candles) < 20:
                print(f"[ROW-SKIP] {symbol}: insufficient candles")
                continue

            candles = normalize_candles(raw_candles)

            if not _debug_payload_logged:
                print(f"[DEBUG] sample payload keys for {symbol}: {list(payload.keys())}")
                if raw_candles:
                    print(f"[DEBUG] sample candle type for {symbol}: {type(raw_candles[-1]).__name__}")
                    print(f"[DEBUG] sample candle value for {symbol}: {raw_candles[-1]}")
                _debug_payload_logged = True

            price = safe_float(payload.get("price"), 0.0)
            vwap = safe_float(payload.get("vwap"), 0.0)
            spread_bps = safe_float(payload.get("spread_bps"), 0.0)

            if price <= 0.0:
                print(f"[ROW-SKIP] {symbol}: invalid price")
                continue

            if vwap <= 0.0:
                vwap = price

            row = dict(payload)
            row["symbol"] = str(payload.get("symbol", symbol)).upper()
            row["price"] = price
            row["vwap"] = vwap
            row["spread_bps"] = spread_bps
            row["candles"] = candles
            rows.append(row)

            print(
                f"[ROW-OK] {symbol}: "
                f"price={price:.6f}, "
                f"vwap={vwap:.6f}, "
                f"spread_bps={spread_bps:.2f}, "
                f"spread_src={str(payload.get('spread_source', 'unknown'))}, "
                f"candles={len(candles)}"
            )

        except Exception as exc:
            print(f"[ROW-ERROR] {symbol}: {exc}")
            continue

    return rows


def safe_get_open_positions_count() -> int:
    try:
        return len(position_manager.get_open_positions())
    except Exception:
        return 0


def safe_get_closed_positions_count() -> int:
    try:
        return len(position_manager.get_closed_positions())
    except Exception:
        return 0


def persist_state(summary: Dict[str, Any]) -> None:
    try:
        with SUMMARY_FILE.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        with POSITIONS_FILE.open("w", encoding="utf-8") as f:
            json.dump(position_manager.get_open_positions(), f, indent=2)

        with CLOSED_TRADES_FILE.open("w", encoding="utf-8") as f:
            json.dump(position_manager.get_closed_positions(), f, indent=2)
    except Exception as exc:
        print(f"[WARN] Could not persist artifact state: {exc}")


def passes_optimizer_gate(row: Dict[str, Any], profile: Dict[str, float]) -> bool:
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    pressure_acceleration = safe_float(row.get("pressure_acceleration"), 0.0)
    spread_bps_abs = abs(safe_float(row.get("spread_bps"), 0.0))
    regime = str(row.get("regime", "NEUTRAL")).upper()
    reversion_window_score = safe_float(row.get("reversion_window_score"), 0.0)
    reversion_window_pass = bool(row.get("reversion_window_pass", False))
    elasticity_score = safe_float(row.get("elasticity_score"), 0.0)

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False
    if confluence_score < profile["min_confluence_to_reach_optimizer"]:
        return False
    if spread_bps_abs < profile["min_abs_spread_bps_to_reach_optimizer"]:
        return False
    if not reversion_window_pass:
        return False
    if reversion_window_score < profile["min_reversion_window_score"]:
        return False
    if elasticity_score < profile["min_elasticity_score"]:
        return False
    if (
        pressure_score < profile["min_pressure_to_reach_optimizer"]
        and pressure_acceleration < profile["min_accel_to_reach_optimizer"]
    ):
        return False
    return True


def passes_execution_gate(row: Dict[str, Any], profile: Dict[str, float]) -> bool:
    trade_score = safe_float(row.get("trade_score"), 0.0)
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    pressure_acceleration = safe_float(row.get("pressure_acceleration"), 0.0)
    vwap_dev_abs = safe_float(row.get("vwap_dev_abs"), 0.0)
    regime = str(row.get("regime", "NEUTRAL")).upper()
    tier = str(row.get("signal_tier", "WATCH")).upper()
    reversion_window_score = safe_float(row.get("reversion_window_score"), 0.0)
    reversion_window_pass = bool(row.get("reversion_window_pass", False))
    elasticity_score = safe_float(row.get("elasticity_score"), 0.0)

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False
    if not reversion_window_pass:
        return False
    if reversion_window_score < profile["min_reversion_window_score"]:
        return False
    if elasticity_score < profile["min_elasticity_score"]:
        return False

    if tier == "ELITE":
        return (
            confluence_score >= max(0.88, profile["min_confluence_to_execute"])
            and pressure_score >= max(0.30, profile["min_pressure_to_execute"])
            and vwap_dev_abs >= profile["min_vwap_dev_abs_to_execute"]
        )

    if tier == "QUALIFIED":
        if trade_score < profile["min_trade_score_to_execute"]:
            return False
        if confluence_score < profile["min_confluence_to_execute"]:
            return False
        if vwap_dev_abs < profile["min_vwap_dev_abs_to_execute"]:
            return False
        if pressure_score >= profile["min_pressure_to_execute"]:
            return True
        if pressure_acceleration >= profile["min_accel_or_pressure_boost"]:
            return True
        return False

    return False


ENGINE_MODE = choose_engine_mode()
ACTIVE_PROFILE = ENGINE_PROFILES[ENGINE_MODE]

print("[CSS] Starting live dashboard...")

while True:
    cycle += 1

    try:
        discovered = scanner.scan()

        symbols = [
            str(r["symbol"]).upper()
            for r in discovered
            if str(r.get("venue", "")).upper() == "COINBASE"
        ][:MAX_SYMBOLS_PER_CYCLE]

        print(f"[SCAN] selected Coinbase symbols ({len(symbols)}): {symbols}")

        rows = fetch_assets(symbols)

        if not rows:
            print("Waiting for valid market rows...")
            time.sleep(REFRESH_SECONDS)
            continue

        latest_prices: Dict[str, float] = {
            str(r["symbol"]).upper(): safe_float(r.get("price"), 0.0)
            for r in rows
        }

        features = feature_builder.enrich_rows(rows, {})
        regime_rows = regime_engine.detect(features)
        pressure_rows = call_rows_module(pressure_engine, regime_rows, "OpportunityPressureEngine")
        accel_rows = call_rows_module(accel_engine, pressure_rows, "PressureAccelerationEngine")
        confluence_rows = call_rows_module(confluence_engine, accel_rows, "SignalConfluenceEngine")
        vwap_rows = vwap_engine.enrich_rows(confluence_rows)
        elastic_rows = elasticity_engine.enrich_rows(vwap_rows)
        reversion_rows = reversion_window_engine.enrich_rows(elastic_rows)
        sweep_rows = call_rows_module(sweep_engine, reversion_rows, "LiquiditySweepDetector")
        ranked = ai.rank_opportunities(sweep_rows)

        signal_map = {str(r["symbol"]).upper(): r for r in sweep_rows}

        merged: List[Dict[str, Any]] = []
        for r in ranked:
            symbol = str(r.get("symbol", "")).upper()
            p = signal_map.get(symbol, {})
            regime = str(p.get("regime", "NEUTRAL")).upper()

            base_ai_score = safe_float(r.get("score"), 0.0)
            pressure_score = safe_float(p.get("pressure_score"), 0.0)
            pressure_acceleration = safe_float(p.get("pressure_acceleration"), 0.0)
            confluence_score = safe_float(p.get("confluence_score"), 0.0)
            vwap_dev_abs = safe_float(p.get("vwap_dev_abs"), 0.0)
            reversion_window_score = safe_float(p.get("reversion_window_score"), 0.0)
            elasticity_score = safe_float(p.get("elasticity_score"), 0.0)

            fused_score = blended_conviction_score(
                base_ai_score=base_ai_score,
                confluence_score=confluence_score,
                pressure_score=pressure_score,
                pressure_acceleration=pressure_acceleration,
                regime=regime,
                vwap_dev_abs=vwap_dev_abs,
                reversion_window_score=reversion_window_score,
                elasticity_score=elasticity_score,
            )

            merged.append(
                {
                    "symbol": symbol,
                    "score": fused_score,
                    "base_ai_score": base_ai_score,
                    "pressure_score": pressure_score,
                    "pressure_acceleration": pressure_acceleration,
                    "confluence_score": confluence_score,
                    "confluence_allow_trade": bool(p.get("confluence_allow_trade", False)),
                    "spread_bps": safe_float(p.get("spread_bps"), 0.0),
                    "regime": regime,
                    "regime_alignment": regime_alignment_score(regime),
                    "vwap_dev": safe_float(p.get("vwap_dev"), 0.0),
                    "vwap_dev_abs": vwap_dev_abs,
                    "reversion_window_score": reversion_window_score,
                    "reversion_window_pass": bool(p.get("reversion_window_pass", False)),
                    "vwap_elasticity": safe_float(p.get("vwap_elasticity"), 0.0),
                    "elasticity_score": elasticity_score,
                }
            )

        optimizer_input = [
            row for row in merged
            if row.get("confluence_allow_trade", False) and passes_optimizer_gate(row, ACTIVE_PROFILE)
        ]

        if not optimizer_input:
            optimizer_input = sorted(
                merged,
                key=lambda x: (
                    safe_float(x.get("reversion_window_score"), 0.0),
                    safe_float(x.get("elasticity_score"), 0.0),
                    safe_float(x.get("confluence_score"), 0.0),
                    safe_float(x.get("pressure_score"), 0.0),
                    safe_float(x.get("vwap_dev_abs"), 0.0),
                    safe_float(x.get("score"), 0.0),
                ),
                reverse=True,
            )[:1]

        print(
            f"[PIPELINE] merged_rows={len(merged)} "
            f"confluence_pass={sum(1 for x in merged if x.get('confluence_allow_trade', False))} "
            f"optimizer_rows={len(optimizer_input)}"
        )

        optimized = optimizer.optimize(optimizer_input)

        optimized_plus: List[Dict[str, Any]] = []
        opt_map = {str(r.get("symbol", "")).upper(): r for r in optimized}
        for row in optimizer_input:
            symbol = str(row.get("symbol", "")).upper()
            merged_row = dict(row)
            merged_row.update(opt_map.get(symbol, {}))
            if "reversion_window_score" not in merged_row:
                merged_row["reversion_window_score"] = safe_float(row.get("reversion_window_score"), 0.0)
            if "reversion_window_pass" not in merged_row:
                merged_row["reversion_window_pass"] = bool(row.get("reversion_window_pass", False))
            if "vwap_elasticity" not in merged_row:
                merged_row["vwap_elasticity"] = safe_float(row.get("vwap_elasticity"), 0.0)
            if "elasticity_score" not in merged_row:
                merged_row["elasticity_score"] = safe_float(row.get("elasticity_score"), 0.0)
            optimized_plus.append(merged_row)

        classified = elite_classifier.classify(optimized_plus)

        classified = sorted(
            classified,
            key=lambda x: (
                safe_float(x.get("trade_score"), 0.0),
                1 if str(x.get("signal_tier", "WATCH")).upper() == "ELITE" else 0,
                safe_float(x.get("reversion_window_score"), 0.0),
                safe_float(x.get("elasticity_score"), 0.0),
                safe_float(x.get("confluence_score"), 0.0),
                safe_float(x.get("pressure_score"), 0.0),
                safe_float(x.get("vwap_dev_abs"), 0.0),
            ),
            reverse=True,
        )

        passing_execution_gate = [
            r for r in classified
            if str(r.get("decision", "")).upper() == "TRADE"
            and passes_execution_gate(r, ACTIVE_PROFILE)
        ][:MAX_TRADES_PER_CYCLE]

        execution_audit: List[str] = []
        opened_this_cycle = 0

        for r in passing_execution_gate:
            symbol = str(r["symbol"]).upper()
            price = safe_float(latest_prices.get(symbol, 0.0), 0.0)
            trade_score = safe_float(r.get("trade_score"), 0.0)

            if price <= 0.0:
                execution_audit.append(f"{symbol}: skipped_invalid_price")
                continue

            if position_manager.has_open_position(symbol):
                execution_audit.append(f"{symbol}: skipped_already_open")
                continue

            qty = 10.0 / price

            position_manager.open_long_position(
                symbol=symbol,
                quantity=qty,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now(),
            )

            opened_this_cycle += 1
            execution_audit.append(f"{symbol}: OPENED")

            print(
                f"[OPEN] {symbol} | price={price:.6f} | qty={qty:.8f} | "
                f"trade={trade_score:.2f} | tier={str(r.get('signal_tier', 'WATCH')).upper()} | "
                f"vwap_dev={safe_float(r.get('vwap_dev_abs'), 0.0):.4f} | "
                f"rwin={safe_float(r.get('reversion_window_score'), 0.0):.2f} | "
                f"elas={safe_float(r.get('elasticity_score'), 0.0):.2f} | "
                f"confluence={safe_float(r.get('confluence_score'), 0.0):.2f} | "
                f"pressure={safe_float(r.get('pressure_score'), 0.0):.2f} | "
                f"accel={safe_float(r.get('pressure_acceleration'), 0.0):.2f}"
            )

        closed_positions = position_manager.update_positions(
            latest_prices=latest_prices,
            cycle_no=cycle,
            now=now(),
        )

        cycle_realized_pnl = 0.0
        for trade in closed_positions:
            pnl = safe_float(trade.get("realized_pnl_usd"), 0.0)
            cycle_realized_pnl += pnl
            estimated_equity += pnl
            _last_closed_trade = trade
            print(
                f"[CLOSE] {trade.get('symbol', '?')} | "
                f"reason={trade.get('exit_reason', 'unknown')} | "
                f"pnl={pnl:.4f}"
            )

        open_positions_count = safe_get_open_positions_count()
        closed_positions_count = safe_get_closed_positions_count()

        summary = {
            "timestamp_utc": now(),
            "cycle_no": cycle,
            "engine_mode": ENGINE_MODE,
            "engine_profile": ACTIVE_PROFILE,
            "starting_capital_usd": starting_capital,
            "estimated_equity_usd": estimated_equity,
            "cycle_realized_pnl_usd": cycle_realized_pnl,
            "symbols_scanned": len(symbols),
            "signals_scanned": len(merged),
            "signals_passed_confluence": sum(
                1 for x in merged if x.get("confluence_allow_trade", False)
            ),
            "signals_passed_optimizer_gate": len(
                [x for x in merged if x.get("confluence_allow_trade", False) and passes_optimizer_gate(x, ACTIVE_PROFILE)]
            ),
            "signals_passed_execution_gate": len(passing_execution_gate),
            "opened_this_cycle": opened_this_cycle,
            "open_positions": open_positions_count,
            "closed_positions": closed_positions_count,
            "execution_audit": execution_audit,
            "max_symbols_per_cycle": MAX_SYMBOLS_PER_CYCLE,
            "max_trades_per_cycle": MAX_TRADES_PER_CYCLE,
        }

        persist_state(summary)

        clear()

        print("======================================")
        print("   CAPITAL STRATA SYSTEMS DASHBOARD")
        print("======================================\n")
        print("Cycle:", cycle)
        print("Equity:", round(estimated_equity, 2))
        print("Engine mode:", ENGINE_MODE.upper())
        print("Symbols scanned:", len(symbols), f"(cap={MAX_SYMBOLS_PER_CYCLE})")
        print("Trade cap:", MAX_TRADES_PER_CYCLE)
        print("Execution style: CONDITION-DRIVEN / SESSION-LOCKED POLICY")
        print("Trades this cycle: top condition-qualified signals only")
        print("Signals passed final gate:", len(passing_execution_gate))
        print("Opened this cycle:", opened_this_cycle)
        print("Open positions:", open_positions_count)
        print("Closed positions:", closed_positions_count)
        print("Cycle realized PnL:", round(cycle_realized_pnl, 4))
        print("Symbols:", symbols)

        if _last_closed_trade:
            print(
                "\nLAST CLOSE → "
                f"{_last_closed_trade.get('symbol', '?')} | "
                f"pnl={safe_float(_last_closed_trade.get('realized_pnl_usd'), 0.0):.4f} | "
                f"reason={_last_closed_trade.get('exit_reason', 'unknown')}"
            )

        print("\nAI SIGNAL SCANNER\n")
        if not classified:
            print("No optimized rows available this cycle.")
        else:
            for r in classified[:15]:
                exec_gate = "PASS" if passes_execution_gate(r, ACTIVE_PROFILE) else "HOLD"
                print(
                    f"{r['symbol']:10}"
                    f" regime={str(r.get('regime', 'NEUTRAL')):12}"
                    f" tier={str(r.get('signal_tier', 'WATCH')).upper():10}"
                    f" base={safe_float(r.get('base_ai_score', 0.0)):.2f}"
                    f" score={safe_float(r.get('score'), 0.0):.2f}"
                    f" pressure={safe_float(r.get('pressure_score'), 0.0):.2f}"
                    f" accel={safe_float(r.get('pressure_acceleration'), 0.0):.2f}"
                    f" vwap_dev={safe_float(r.get('vwap_dev_abs'), 0.0):.4f}"
                    f" rwin={safe_float(r.get('reversion_window_score'), 0.0):.2f}"
                    f" elas={safe_float(r.get('elasticity_score'), 0.0):.2f}"
                    f" confluence={safe_float(r.get('confluence_score'), 0.0):.2f}"
                    f" trade={safe_float(r.get('trade_score'), 0.0):.2f}"
                    f" decision={str(r.get('decision', 'WATCH')).upper()}"
                    f" gate={exec_gate}"
                )

        print("\nEXECUTION AUDIT\n")
        if execution_audit:
            for line in execution_audit:
                print(line)
        else:
            print("No execution actions this cycle.")

        print(f"\nRefreshing in {REFRESH_SECONDS} seconds...\n")
        time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("CSS stopped")
        break

    except Exception as e:
        print("CSS ERROR:", e)
        traceback.print_exc()
        time.sleep(REFRESH_SECONDS)