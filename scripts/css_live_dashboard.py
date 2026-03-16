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
MAX_TRADES_PER_CYCLE = 3
REFRESH_SECONDS = 10

MAX_OPEN_POSITIONS_TOTAL = 5
MAX_OPEN_POSITIONS_FX = 3
MAX_OPEN_POSITIONS_CRYPTO = 2
MAX_OPEN_POSITIONS_OTHER = 1

GLOBAL_TAKE_PROFIT_PCT = 0.014
GLOBAL_STOP_LOSS_PCT = 0.012
GLOBAL_MAX_HOLD_CYCLES = 5

ELITE_TAKE_PROFIT_PCT = 0.022
QUALIFIED_TAKE_PROFIT_PCT = 0.012
ELITE_MAX_HOLD_CYCLES = 6
QUALIFIED_MAX_HOLD_CYCLES = 4

BASE_TRADE_NOTIONAL_USD = 10.0
ELITE_TRADE_NOTIONAL_USD = 12.0
QUALIFIED_TRADE_NOTIONAL_USD = 10.0
WATCHLIST_TRADE_NOTIONAL_USD = 8.0

REENTRY_COOLDOWN_CYCLES = 2

LIQUIDITY_QUALITY_FLOOR = 0.34
JUNK_PENALTY_STRICT_FLOOR = 0.24

ENGINE_PROFILES: Dict[str, Dict[str, float]] = {
    "safe/test": {
        "min_confluence_to_reach_optimizer": 0.82,
        "min_pressure_to_reach_optimizer": 0.22,
        "min_accel_to_reach_optimizer": 0.10,
        "max_abs_spread_bps_to_reach_optimizer": 20.0,
        "min_trade_score_to_execute": 0.58,
        "min_confluence_to_execute": 0.82,
        "min_pressure_to_execute": 0.22,
        "min_accel_or_pressure_boost": 0.10,
        "min_vwap_dev_abs_to_execute": 0.013,
        "min_reversion_window_score": 0.58,
        "min_elasticity_score": 0.24,
        "min_directional_fit_to_execute": 0.64,
        "min_entry_quality_to_execute": 0.66,
        "min_liquidity_quality_to_execute": 0.56,
    },
    "conservative": {
        "min_confluence_to_reach_optimizer": 0.76,
        "min_pressure_to_reach_optimizer": 0.18,
        "min_accel_to_reach_optimizer": 0.08,
        "max_abs_spread_bps_to_reach_optimizer": 18.0,
        "min_trade_score_to_execute": 0.54,
        "min_confluence_to_execute": 0.76,
        "min_pressure_to_execute": 0.18,
        "min_accel_or_pressure_boost": 0.08,
        "min_vwap_dev_abs_to_execute": 0.011,
        "min_reversion_window_score": 0.52,
        "min_elasticity_score": 0.20,
        "min_directional_fit_to_execute": 0.58,
        "min_entry_quality_to_execute": 0.60,
        "min_liquidity_quality_to_execute": 0.50,
    },
    "balanced": {
        "min_confluence_to_reach_optimizer": 0.70,
        "min_pressure_to_reach_optimizer": 0.16,
        "min_accel_to_reach_optimizer": 0.06,
        "max_abs_spread_bps_to_reach_optimizer": 16.0,
        "min_trade_score_to_execute": 0.50,
        "min_confluence_to_execute": 0.70,
        "min_pressure_to_execute": 0.16,
        "min_accel_or_pressure_boost": 0.06,
        "min_vwap_dev_abs_to_execute": 0.010,
        "min_reversion_window_score": 0.45,
        "min_elasticity_score": 0.18,
        "min_directional_fit_to_execute": 0.52,
        "min_entry_quality_to_execute": 0.55,
        "min_liquidity_quality_to_execute": 0.44,
    },
    "aggressive": {
        "min_confluence_to_reach_optimizer": 0.64,
        "min_pressure_to_reach_optimizer": 0.12,
        "min_accel_to_reach_optimizer": 0.04,
        "max_abs_spread_bps_to_reach_optimizer": 14.0,
        "min_trade_score_to_execute": 0.46,
        "min_confluence_to_execute": 0.64,
        "min_pressure_to_execute": 0.12,
        "min_accel_or_pressure_boost": 0.04,
        "min_vwap_dev_abs_to_execute": 0.008,
        "min_reversion_window_score": 0.40,
        "min_elasticity_score": 0.14,
        "min_directional_fit_to_execute": 0.46,
        "min_entry_quality_to_execute": 0.50,
        "min_liquidity_quality_to_execute": 0.38,
    },
    "opportunistic/expansion": {
        "min_confluence_to_reach_optimizer": 0.58,
        "min_pressure_to_reach_optimizer": 0.10,
        "min_accel_to_reach_optimizer": 0.03,
        "max_abs_spread_bps_to_reach_optimizer": 12.0,
        "min_trade_score_to_execute": 0.42,
        "min_confluence_to_execute": 0.58,
        "min_pressure_to_execute": 0.10,
        "min_accel_or_pressure_boost": 0.03,
        "min_vwap_dev_abs_to_execute": 0.006,
        "min_reversion_window_score": 0.36,
        "min_elasticity_score": 0.12,
        "min_directional_fit_to_execute": 0.42,
        "min_entry_quality_to_execute": 0.46,
        "min_liquidity_quality_to_execute": 0.34,
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

MAJOR_CRYPTO_BASES = {
    "BTC", "ETH", "SOL", "XRP", "ADA", "AVAX", "LINK", "DOGE", "LTC",
    "BCH", "UNI", "AAVE", "ATOM", "DOT", "MATIC", "NEAR", "ETC",
    "XLM", "ALGO", "HBAR", "FIL"
}

MEME_OR_THIN_KEYWORDS = {
    "PEPE", "DOG", "FART", "TRUMP", "PENGU", "FLOKI", "BONK",
    "SHIB", "WIF", "MOG", "BRETT", "TURBO", "MEME"
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
    take_profit_pct=GLOBAL_TAKE_PROFIT_PCT,
    stop_loss_pct=GLOBAL_STOP_LOSS_PCT,
    max_hold_cycles=GLOBAL_MAX_HOLD_CYCLES,
)

starting_capital = 200.0
estimated_equity = starting_capital
cycle = 0
_debug_payload_logged = False
recent_exit_cycle_by_symbol: Dict[str, int] = {}


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
                lower=0.006,
                ideal_low=0.012,
                ideal_high=0.055,
                upper=0.120,
            )

            pressure_fit = clamp01(pressure / 0.35)
            accel_fit = clamp01(accel / 0.10)
            confluence_fit = clamp01(confluence / 0.85)

            regime_fit_map = {
                "MEAN_REVERSION": 1.00,
                "RANGE": 0.92,
                "NEUTRAL": 0.84,
                "VOLATILE": 0.78,
                "TREND": 0.74,
                "BREAKOUT": 0.68,
            }
            regime_fit = regime_fit_map.get(regime, 0.55)

            reversion_window_score = clamp01(
                0.30 * deviation_fit
                + 0.16 * pressure_fit
                + 0.08 * accel_fit
                + 0.20 * confluence_fit
                + 0.12 * regime_fit
                + 0.14 * elasticity_score
            )

            reversion_window_pass = (
                deviation_fit >= 0.38
                and confluence_fit >= 0.52
                and reversion_window_score >= 0.34
            )

            new_row = dict(row)
            new_row["reversion_window_score"] = reversion_window_score
            new_row["reversion_window_pass"] = reversion_window_pass
            enriched.append(new_row)

        return enriched


class MicroTrendAlignmentEngine:
    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            candles = row.get("candles", [])
            last5 = candles[-5:] if len(candles) >= 5 else candles[-3:]

            closes = [safe_float(c.get("close"), 0.0) for c in last5 if isinstance(c, dict)]
            highs = [safe_float(c.get("high"), 0.0) for c in last5 if isinstance(c, dict)]
            lows = [safe_float(c.get("low"), 0.0) for c in last5 if isinstance(c, dict)]
            price = safe_float(row.get("price"), 0.0)
            vwap = safe_float(row.get("vwap"), 0.0)

            micro_trend_score = 0.5
            micro_bias = "NEUTRAL"

            if len(closes) >= 3:
                up_steps = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
                down_steps = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i - 1])

                range_span = max(highs) - min(lows) if highs and lows else 0.0
                move_span = abs(closes[-1] - closes[0]) if closes else 0.0
                efficiency = clamp01(move_span / range_span) if range_span > 0 else 0.0

                if price >= vwap:
                    micro_trend_score = clamp01(0.45 + 0.12 * up_steps + 0.10 * efficiency - 0.08 * down_steps)
                    micro_bias = "UP"
                else:
                    micro_trend_score = clamp01(0.45 + 0.12 * down_steps + 0.10 * efficiency - 0.08 * up_steps)
                    micro_bias = "DOWN"

            new_row = dict(row)
            new_row["micro_trend_score"] = micro_trend_score
            new_row["micro_bias"] = micro_bias
            new_row["micro_trend_pass"] = micro_trend_score >= 0.50
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
            micro_trend_score = safe_float(row.get("micro_trend_score"), 0.0)
            entry_quality_score = safe_float(row.get("entry_quality_score"), 0.0)
            directional_long_fit = safe_float(row.get("directional_long_fit"), 0.0)
            liquidity_quality_score = safe_float(row.get("liquidity_quality_score"), 0.0)
            junk_penalty_score = safe_float(row.get("junk_penalty_score"), 0.0)

            tier = "WATCH"

            if (
                trade_score >= 0.42
                and reversion_window_score >= 0.34
                and micro_trend_score >= 0.48
                and directional_long_fit >= 0.40
                and entry_quality_score >= 0.42
                and liquidity_quality_score >= 0.34
                and junk_penalty_score <= 0.60
            ):
                tier = "QUALIFIED"

            if (
                confluence >= 0.82
                and pressure >= 0.22
                and vwap_dev_abs >= 0.010
                and trade_score >= 0.50
                and reversion_window_score >= 0.50
                and elasticity_score >= 0.18
                and micro_trend_score >= 0.58
                and directional_long_fit >= 0.58
                and entry_quality_score >= 0.58
                and liquidity_quality_score >= 0.50
                and junk_penalty_score <= 0.36
            ):
                tier = "ELITE"

            new_row = dict(row)
            new_row["signal_tier"] = tier
            classified.append(new_row)

        return classified


vwap_engine = VWAPDeviationEngine()
reversion_window_engine = VWAPReversionWindowEngine()
micro_trend_engine = MicroTrendAlignmentEngine()
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
    micro_trend_score: float,
) -> float:
    regime_score = regime_alignment_score(regime)
    score = (
        0.10 * clamp01(base_ai_score)
        + 0.22 * clamp01(confluence_score)
        + 0.16 * clamp01(pressure_score)
        + 0.08 * clamp01(pressure_acceleration)
        + 0.08 * clamp01(regime_score)
        + 0.10 * clamp01(vwap_dev_abs * 30.0)
        + 0.12 * clamp01(reversion_window_score)
        + 0.07 * clamp01(elasticity_score)
        + 0.07 * clamp01(micro_trend_score)
    )
    return clamp01(score)


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


def infer_asset_class(symbol: str, venue: str) -> str:
    s = str(symbol).upper()
    v = str(venue).upper()

    if v in {"OANDA", "FOREX", "FX", "ALPACA_FX", "QUESTRADE_FX"}:
        return "FX"
    if "_" in s:
        return "FX"

    crypto_quote_suffixes = (
        "-USD", "-USDC", "-USDT", "-BTC", "-ETH", "-EUR", "-GBP"
    )
    if v in {"COINBASE", "KRAKEN", "BINANCE", "CRYPTO"} or s.endswith(crypto_quote_suffixes):
        return "CRYPTO"

    return "OTHER"


def extract_symbol_base(symbol: str) -> str:
    s = str(symbol).upper()
    for sep in ("-", "_", "/"):
        if sep in s:
            return s.split(sep)[0]
    return s


def is_meme_or_thin_name(symbol: str) -> bool:
    base = extract_symbol_base(symbol)
    return any(key in base for key in MEME_OR_THIN_KEYWORDS)


def is_major_crypto(symbol: str) -> bool:
    return extract_symbol_base(symbol) in MAJOR_CRYPTO_BASES


def summarize_selected_assets(selected_rows: List[Dict[str, Any]]) -> str:
    counts = {"FX": 0, "CRYPTO": 0, "OTHER": 0}
    for row in selected_rows:
        cls = str(row.get("asset_class", "OTHER")).upper()
        counts[cls] = counts.get(cls, 0) + 1
    return f"FX={counts.get('FX',0)} CRYPTO={counts.get('CRYPTO',0)} OTHER={counts.get('OTHER',0)}"


def count_open_positions_by_asset_class() -> Dict[str, int]:
    counts = {"FX": 0, "CRYPTO": 0, "OTHER": 0, "TOTAL": 0}
    try:
        open_positions = position_manager.get_open_positions()
    except Exception:
        return counts

    for pos in open_positions:
        if str(pos.get("status", "OPEN")).upper() != "OPEN":
            continue
        asset_class = str(pos.get("asset_class", "")).upper()
        if asset_class not in {"FX", "CRYPTO", "OTHER"}:
            asset_class = infer_asset_class(
                symbol=str(pos.get("symbol", "")),
                venue=str(pos.get("venue", "")),
            )
        counts[asset_class] = counts.get(asset_class, 0) + 1
        counts["TOTAL"] += 1
    return counts


def capacity_available_for_asset_class(asset_class: str, counts: Dict[str, int]) -> bool:
    asset_class = str(asset_class).upper()
    if counts.get("TOTAL", 0) >= MAX_OPEN_POSITIONS_TOTAL:
        return False
    if asset_class == "FX":
        return counts.get("FX", 0) < MAX_OPEN_POSITIONS_FX
    if asset_class == "CRYPTO":
        return counts.get("CRYPTO", 0) < MAX_OPEN_POSITIONS_CRYPTO
    return counts.get("OTHER", 0) < MAX_OPEN_POSITIONS_OTHER


def call_rows_module(module: Any, rows: List[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    if hasattr(module, "enrich_rows"):
        return module.enrich_rows(rows)
    if hasattr(module, "enrich"):
        return module.enrich(rows)
    if hasattr(module, "detect"):
        return module.detect(rows)

    print(f"[PIPELINE-WARN] {label}: no compatible row method found, passing rows through")
    return rows


def infer_liquidity_proxy(
    *,
    asset_class: str,
    spread_bps: float,
    spread_source: str,
    symbol: str,
) -> float:
    asset_class = str(asset_class).upper()
    spread_bps = abs(spread_bps)
    spread_source = str(spread_source).lower()

    if asset_class == "FX":
        base = 0.82
    elif asset_class == "CRYPTO":
        base = 0.58 if is_major_crypto(symbol) else 0.42
    else:
        base = 0.36

    spread_penalty = clamp01(spread_bps / 25.0) * 0.48
    if spread_source in {"fallback", "unknown"}:
        spread_penalty += 0.08

    if is_meme_or_thin_name(symbol):
        spread_penalty += 0.16

    return clamp01(base - spread_penalty)


def compute_junk_penalty_score(
    *,
    symbol: str,
    asset_class: str,
    spread_bps: float,
    spread_source: str,
) -> float:
    penalty = 0.0
    asset_class = str(asset_class).upper()
    spread_bps = abs(spread_bps)
    spread_source = str(spread_source).lower()

    if asset_class == "OTHER":
        penalty += 0.18

    if asset_class == "CRYPTO" and not is_major_crypto(symbol):
        penalty += 0.12

    if is_meme_or_thin_name(symbol):
        penalty += 0.28

    penalty += clamp01(spread_bps / 20.0) * 0.34

    if spread_source in {"fallback", "unknown"}:
        penalty += 0.08

    return clamp01(penalty)


def compute_liquidity_quality_score(row: Dict[str, Any]) -> float:
    symbol = str(row.get("symbol", "")).upper()
    asset_class = str(row.get("asset_class", "OTHER")).upper()
    spread_bps = abs(safe_float(row.get("spread_bps"), 0.0))
    spread_source = str(row.get("spread_source", "unknown")).lower()
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    elasticity_score = safe_float(row.get("elasticity_score"), 0.0)

    liquidity_proxy = infer_liquidity_proxy(
        asset_class=asset_class,
        spread_bps=spread_bps,
        spread_source=spread_source,
        symbol=symbol,
    )
    junk_penalty = compute_junk_penalty_score(
        symbol=symbol,
        asset_class=asset_class,
        spread_bps=spread_bps,
        spread_source=spread_source,
    )

    score = (
        0.58 * liquidity_proxy
        + 0.18 * clamp01(confluence_score)
        + 0.10 * clamp01(pressure_score)
        + 0.08 * clamp01(elasticity_score)
        + (0.10 if asset_class == "FX" else 0.0)
        + (0.08 if asset_class == "CRYPTO" and is_major_crypto(symbol) else 0.0)
    ) - 0.42 * junk_penalty

    return clamp01(score)


def fetch_assets(selected_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    global _debug_payload_logged

    rows: List[Dict[str, Any]] = []

    for selected in selected_rows:
        symbol = str(selected.get("symbol", "")).upper()
        venue = str(selected.get("venue", "UNKNOWN")).upper()
        asset_class = str(selected.get("asset_class", "OTHER")).upper()

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
            spread_source = str(payload.get("spread_source", "unknown")).lower()

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
            row["spread_source"] = spread_source
            row["venue"] = venue
            row["asset_class"] = asset_class
            row["candles"] = candles
            rows.append(row)

            print(
                f"[ROW-OK] {symbol}: "
                f"venue={venue}, "
                f"asset={asset_class}, "
                f"price={price:.6f}, "
                f"vwap={vwap:.6f}, "
                f"spread_bps={spread_bps:.2f}, "
                f"spread_src={spread_source}, "
                f"candles={len(candles)}"
            )

        except Exception as exc:
            print(f"[ROW-ERROR] {symbol}: {exc}")
            continue

    return rows


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


def apply_post_open_overrides(
    symbol: str,
    price: float,
    signal_tier: str,
    asset_class: str,
    venue: str,
    entry_quality_score: float,
) -> None:
    try:
        open_positions = position_manager.get_open_positions()
        for pos in open_positions:
            if str(pos.get("symbol", "")).upper() != symbol:
                continue
            if str(pos.get("status", "OPEN")).upper() != "OPEN":
                continue

            tier = str(signal_tier).upper()
            if tier == "ELITE":
                pos["take_profit_price"] = price * (1.0 + ELITE_TAKE_PROFIT_PCT)
                pos["max_hold_cycles"] = ELITE_MAX_HOLD_CYCLES
            else:
                pos["take_profit_price"] = price * (1.0 + QUALIFIED_TAKE_PROFIT_PCT)
                pos["max_hold_cycles"] = QUALIFIED_MAX_HOLD_CYCLES

            pos["signal_tier"] = tier
            pos["asset_class"] = str(asset_class).upper()
            pos["venue"] = str(venue).upper()
            pos["entry_quality_score"] = entry_quality_score
            break
    except Exception:
        pass


def compute_directional_long_fit(row: Dict[str, Any]) -> float:
    regime = str(row.get("regime", "NEUTRAL")).upper()
    vwap_dev = safe_float(row.get("vwap_dev"), 0.0)
    vwap_dev_abs = safe_float(row.get("vwap_dev_abs"), 0.0)
    pressure = safe_float(row.get("pressure_score"), 0.0)
    accel = safe_float(row.get("pressure_acceleration"), 0.0)
    micro_trend_score = safe_float(row.get("micro_trend_score"), 0.0)
    micro_bias = str(row.get("micro_bias", "NEUTRAL")).upper()
    elasticity_score = safe_float(row.get("elasticity_score"), 0.0)
    liquidity_sweep_down = bool(row.get("liquidity_sweep_down", False))
    liquidity_sweep_up = bool(row.get("liquidity_sweep_up", False))

    score = 0.35

    if regime in {"MEAN_REVERSION", "RANGE", "NEUTRAL"}:
        if vwap_dev < 0:
            score += 0.24
        else:
            score -= 0.12

        if micro_bias == "DOWN":
            score += 0.12

        if liquidity_sweep_down:
            score += 0.12

        if 0.006 <= vwap_dev_abs <= 0.040:
            score += 0.10

        score += 0.08 * clamp01(elasticity_score)
        score += 0.06 * clamp01(micro_trend_score)

    elif regime in {"TREND", "BREAKOUT"}:
        if vwap_dev > 0:
            score += 0.22
        else:
            score -= 0.08

        if micro_bias == "UP":
            score += 0.16

        if liquidity_sweep_up:
            score += 0.08

        score += 0.12 * clamp01(pressure / 0.30)
        score += 0.10 * clamp01(accel / 0.10)
        score += 0.08 * clamp01(micro_trend_score)

    elif regime == "VOLATILE":
        if vwap_dev < 0:
            score += 0.12
        if liquidity_sweep_down:
            score += 0.10
        score += 0.08 * clamp01(pressure / 0.30)
        score += 0.08 * clamp01(elasticity_score)
        score += 0.06 * clamp01(micro_trend_score)

    return clamp01(score)


def compute_pre_entry_quality(row: Dict[str, Any]) -> float:
    base_score = safe_float(row.get("score"), 0.0)
    directional_fit = safe_float(row.get("directional_long_fit"), 0.0)
    reversion_window_score = safe_float(row.get("reversion_window_score"), 0.0)
    elasticity_score = safe_float(row.get("elasticity_score"), 0.0)
    micro_trend_score = safe_float(row.get("micro_trend_score"), 0.0)
    liquidity_quality_score = safe_float(row.get("liquidity_quality_score"), 0.0)
    junk_penalty_score = safe_float(row.get("junk_penalty_score"), 0.0)
    spread_bps = abs(safe_float(row.get("spread_bps"), 0.0))
    spread_source = str(row.get("spread_source", "unknown")).lower()

    spread_penalty = clamp01(spread_bps / 30.0) * 0.08
    if spread_source in {"fallback", "unknown"}:
        spread_penalty += 0.02

    score = (
        0.28 * clamp01(base_score)
        + 0.22 * clamp01(directional_fit)
        + 0.16 * clamp01(reversion_window_score)
        + 0.08 * clamp01(elasticity_score)
        + 0.08 * clamp01(micro_trend_score)
        + 0.14 * clamp01(liquidity_quality_score)
        + 0.04 * clamp01(row.get("confluence_score", 0.0))
    ) - spread_penalty - 0.10 * clamp01(junk_penalty_score)

    return clamp01(score)


def compute_entry_quality_score(row: Dict[str, Any]) -> float:
    trade_score = safe_float(row.get("trade_score"), 0.0)
    base_score = safe_float(row.get("score"), 0.0)
    directional_fit = safe_float(row.get("directional_long_fit"), 0.0)
    reversion_window_score = safe_float(row.get("reversion_window_score"), 0.0)
    elasticity_score = safe_float(row.get("elasticity_score"), 0.0)
    micro_trend_score = safe_float(row.get("micro_trend_score"), 0.0)
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    liquidity_quality_score = safe_float(row.get("liquidity_quality_score"), 0.0)
    junk_penalty_score = safe_float(row.get("junk_penalty_score"), 0.0)
    spread_bps = abs(safe_float(row.get("spread_bps"), 0.0))
    spread_source = str(row.get("spread_source", "unknown")).lower()

    spread_penalty = clamp01(spread_bps / 24.0) * 0.08
    if spread_source in {"fallback", "unknown"}:
        spread_penalty += 0.02

    score = (
        0.23 * clamp01(trade_score)
        + 0.14 * clamp01(base_score)
        + 0.20 * clamp01(directional_fit)
        + 0.12 * clamp01(reversion_window_score)
        + 0.07 * clamp01(elasticity_score)
        + 0.07 * clamp01(micro_trend_score)
        + 0.07 * clamp01(confluence_score)
        + 0.16 * clamp01(liquidity_quality_score)
    ) - spread_penalty - 0.12 * clamp01(junk_penalty_score)

    return clamp01(score)


def determine_trade_notional_usd(row: Dict[str, Any]) -> float:
    tier = str(row.get("signal_tier", "WATCH")).upper()
    entry_quality_score = safe_float(row.get("entry_quality_score"), 0.0)
    liquidity_quality_score = safe_float(row.get("liquidity_quality_score"), 0.0)

    if tier == "ELITE" and entry_quality_score >= 0.70 and liquidity_quality_score >= 0.56:
        return ELITE_TRADE_NOTIONAL_USD
    if tier in {"ELITE", "QUALIFIED"} and entry_quality_score >= 0.56 and liquidity_quality_score >= 0.44:
        return QUALIFIED_TRADE_NOTIONAL_USD
    return WATCHLIST_TRADE_NOTIONAL_USD


def in_reentry_cooldown(symbol: str, current_cycle: int) -> bool:
    last_exit_cycle = recent_exit_cycle_by_symbol.get(symbol)
    if last_exit_cycle is None:
        return False
    return (current_cycle - last_exit_cycle) <= REENTRY_COOLDOWN_CYCLES


def passes_optimizer_gate(row: Dict[str, Any], profile: Dict[str, float]) -> bool:
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    pressure_acceleration = safe_float(row.get("pressure_acceleration"), 0.0)
    spread_bps_abs = abs(safe_float(row.get("spread_bps"), 0.0))
    spread_source = str(row.get("spread_source", "unknown")).lower()
    regime = str(row.get("regime", "NEUTRAL")).upper()
    reversion_window_score = safe_float(row.get("reversion_window_score"), 0.0)
    reversion_window_pass = bool(row.get("reversion_window_pass", False))
    elasticity_score = safe_float(row.get("elasticity_score"), 0.0)
    micro_trend_score = safe_float(row.get("micro_trend_score"), 0.0)
    directional_long_fit = safe_float(row.get("directional_long_fit"), 0.0)
    pre_entry_quality = safe_float(row.get("pre_entry_quality"), 0.0)
    liquidity_quality_score = safe_float(row.get("liquidity_quality_score"), 0.0)
    junk_penalty_score = safe_float(row.get("junk_penalty_score"), 0.0)

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False
    if confluence_score < profile["min_confluence_to_reach_optimizer"]:
        return False
    if spread_source not in {"fallback", "unknown"}:
        if spread_bps_abs > profile["max_abs_spread_bps_to_reach_optimizer"]:
            return False
    if not reversion_window_pass:
        return False
    if reversion_window_score < profile["min_reversion_window_score"]:
        return False
    if elasticity_score < profile["min_elasticity_score"]:
        return False
    if micro_trend_score < 0.46:
        return False
    if directional_long_fit < max(0.36, profile["min_directional_fit_to_execute"] - 0.10):
        return False
    if pre_entry_quality < max(0.36, profile["min_entry_quality_to_execute"] - 0.12):
        return False
    if liquidity_quality_score < LIQUIDITY_QUALITY_FLOOR:
        return False
    if junk_penalty_score > 0.78:
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
    micro_trend_score = safe_float(row.get("micro_trend_score"), 0.0)
    directional_long_fit = safe_float(row.get("directional_long_fit"), 0.0)
    entry_quality_score = safe_float(row.get("entry_quality_score"), 0.0)
    liquidity_quality_score = safe_float(row.get("liquidity_quality_score"), 0.0)
    junk_penalty_score = safe_float(row.get("junk_penalty_score"), 0.0)

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False
    if not reversion_window_pass:
        return False
    if reversion_window_score < profile["min_reversion_window_score"]:
        return False
    if elasticity_score < profile["min_elasticity_score"]:
        return False
    if micro_trend_score < 0.50:
        return False
    if directional_long_fit < profile["min_directional_fit_to_execute"]:
        return False
    if entry_quality_score < profile["min_entry_quality_to_execute"]:
        return False
    if liquidity_quality_score < profile["min_liquidity_quality_to_execute"]:
        return False
    if junk_penalty_score > 0.62:
        return False
    if liquidity_quality_score < JUNK_PENALTY_STRICT_FLOOR:
        return False

    if tier == "ELITE":
        return (
            confluence_score >= max(0.82, profile["min_confluence_to_execute"])
            and pressure_score >= max(0.22, profile["min_pressure_to_execute"])
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


def classify_execution_decision(row: Dict[str, Any], profile: Dict[str, float]) -> str:
    tier = str(row.get("signal_tier", "WATCH")).upper()
    if tier == "ELITE" and passes_execution_gate(row, profile):
        return "TRADE"
    if tier == "QUALIFIED" and passes_execution_gate(row, profile):
        return "TRADE"
    if tier in {"ELITE", "QUALIFIED"}:
        return "ARMED"
    return "WATCH"


ENGINE_MODE = choose_engine_mode()
ACTIVE_PROFILE = ENGINE_PROFILES[ENGINE_MODE]

print("[CSS] Starting live dashboard...")

while True:
    cycle += 1

    try:
        discovered = scanner.scan()

        selected_rows: List[Dict[str, Any]] = []
        seen_symbols = set()

        for raw in discovered:
            symbol = str(raw.get("symbol", "")).upper()
            if not symbol or symbol in seen_symbols:
                continue
            venue = str(raw.get("venue", "UNKNOWN")).upper()
            asset_class = infer_asset_class(symbol=symbol, venue=venue)
            selected_rows.append(
                {
                    "symbol": symbol,
                    "venue": venue,
                    "asset_class": asset_class,
                }
            )
            seen_symbols.add(symbol)
            if len(selected_rows) >= MAX_SYMBOLS_PER_CYCLE:
                break

        symbols = [row["symbol"] for row in selected_rows]

        print(f"[SCAN] selected symbols ({len(symbols)}): {symbols}")
        print(f"[SCAN] asset mix: {summarize_selected_assets(selected_rows)}")

        rows = fetch_assets(selected_rows)

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
        micro_rows = micro_trend_engine.enrich_rows(reversion_rows)
        sweep_rows = call_rows_module(sweep_engine, micro_rows, "LiquiditySweepDetector")
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
            vwap_dev = safe_float(p.get("vwap_dev"), 0.0)
            vwap_dev_abs = safe_float(p.get("vwap_dev_abs"), 0.0)
            reversion_window_score = safe_float(p.get("reversion_window_score"), 0.0)
            elasticity_score = safe_float(p.get("elasticity_score"), 0.0)
            micro_trend_score = safe_float(p.get("micro_trend_score"), 0.0)
            venue = str(p.get("venue", "UNKNOWN")).upper()
            asset_class = str(p.get("asset_class", infer_asset_class(symbol, venue))).upper()
            spread_bps = safe_float(p.get("spread_bps"), 0.0)
            spread_source = str(p.get("spread_source", "unknown")).lower()

            directional_long_fit = compute_directional_long_fit(p)

            fused_score = blended_conviction_score(
                base_ai_score=base_ai_score,
                confluence_score=confluence_score,
                pressure_score=pressure_score,
                pressure_acceleration=pressure_acceleration,
                regime=regime,
                vwap_dev_abs=vwap_dev_abs,
                reversion_window_score=reversion_window_score,
                elasticity_score=elasticity_score,
                micro_trend_score=micro_trend_score,
            )

            merged_row = {
                "symbol": symbol,
                "venue": venue,
                "asset_class": asset_class,
                "score": fused_score,
                "base_ai_score": base_ai_score,
                "pressure_score": pressure_score,
                "pressure_acceleration": pressure_acceleration,
                "confluence_score": confluence_score,
                "confluence_allow_trade": bool(p.get("confluence_allow_trade", False)),
                "spread_bps": spread_bps,
                "spread_source": spread_source,
                "regime": regime,
                "regime_alignment": regime_alignment_score(regime),
                "vwap_dev": vwap_dev,
                "vwap_dev_abs": vwap_dev_abs,
                "reversion_window_score": reversion_window_score,
                "reversion_window_pass": bool(p.get("reversion_window_pass", False)),
                "vwap_elasticity": safe_float(p.get("vwap_elasticity"), 0.0),
                "elasticity_score": elasticity_score,
                "micro_trend_score": micro_trend_score,
                "micro_bias": str(p.get("micro_bias", "NEUTRAL")).upper(),
                "micro_trend_pass": bool(p.get("micro_trend_pass", False)),
                "liquidity_sweep_up": bool(p.get("liquidity_sweep_up", False)),
                "liquidity_sweep_down": bool(p.get("liquidity_sweep_down", False)),
                "directional_long_fit": directional_long_fit,
            }
            merged_row["junk_penalty_score"] = compute_junk_penalty_score(
                symbol=symbol,
                asset_class=asset_class,
                spread_bps=spread_bps,
                spread_source=spread_source,
            )
            merged_row["liquidity_quality_score"] = compute_liquidity_quality_score(merged_row)
            merged_row["pre_entry_quality"] = compute_pre_entry_quality(merged_row)
            merged.append(merged_row)

        optimizer_input = [
            row for row in merged
            if row.get("confluence_allow_trade", False) and passes_optimizer_gate(row, ACTIVE_PROFILE)
        ]

        if not optimizer_input:
            optimizer_input = sorted(
                merged,
                key=lambda x: (
                    safe_float(x.get("pre_entry_quality"), 0.0),
                    safe_float(x.get("liquidity_quality_score"), 0.0),
                    -safe_float(x.get("junk_penalty_score"), 0.0),
                    safe_float(x.get("directional_long_fit"), 0.0),
                    safe_float(x.get("reversion_window_score"), 0.0),
                    safe_float(x.get("elasticity_score"), 0.0),
                    safe_float(x.get("micro_trend_score"), 0.0),
                    safe_float(x.get("confluence_score"), 0.0),
                    safe_float(x.get("pressure_score"), 0.0),
                    safe_float(x.get("vwap_dev_abs"), 0.0),
                    safe_float(x.get("score"), 0.0),
                ),
                reverse=True,
            )[:3]

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
            if "micro_trend_score" not in merged_row:
                merged_row["micro_trend_score"] = safe_float(row.get("micro_trend_score"), 0.0)
            if "micro_bias" not in merged_row:
                merged_row["micro_bias"] = str(row.get("micro_bias", "NEUTRAL")).upper()
            if "directional_long_fit" not in merged_row:
                merged_row["directional_long_fit"] = safe_float(row.get("directional_long_fit"), 0.0)
            if "liquidity_quality_score" not in merged_row:
                merged_row["liquidity_quality_score"] = safe_float(row.get("liquidity_quality_score"), 0.0)
            if "junk_penalty_score" not in merged_row:
                merged_row["junk_penalty_score"] = safe_float(row.get("junk_penalty_score"), 0.0)
            merged_row["entry_quality_score"] = compute_entry_quality_score(merged_row)
            optimized_plus.append(merged_row)

        classified = elite_classifier.classify(optimized_plus)

        classified_plus: List[Dict[str, Any]] = []
        for row in classified:
            new_row = dict(row)
            new_row["decision"] = classify_execution_decision(new_row, ACTIVE_PROFILE)
            classified_plus.append(new_row)

        classified = sorted(
            classified_plus,
            key=lambda x: (
                1 if str(x.get("decision", "WATCH")).upper() == "TRADE" else 0,
                safe_float(x.get("entry_quality_score"), 0.0),
                safe_float(x.get("liquidity_quality_score"), 0.0),
                -safe_float(x.get("junk_penalty_score"), 0.0),
                safe_float(x.get("trade_score"), 0.0),
                1 if str(x.get("signal_tier", "WATCH")).upper() == "ELITE" else 0,
                safe_float(x.get("directional_long_fit"), 0.0),
                safe_float(x.get("reversion_window_score"), 0.0),
                safe_float(x.get("elasticity_score"), 0.0),
                safe_float(x.get("micro_trend_score"), 0.0),
                safe_float(x.get("confluence_score"), 0.0),
                safe_float(x.get("pressure_score"), 0.0),
                safe_float(x.get("vwap_dev_abs"), 0.0),
            ),
            reverse=True,
        )

        passing_execution_gate = [
            r for r in classified
            if passes_execution_gate(r, ACTIVE_PROFILE)
        ]

        open_counts = count_open_positions_by_asset_class()

        execution_audit: List[str] = []
        opened_this_cycle = 0
        eligible_after_asset_caps = 0

        for r in passing_execution_gate:
            if opened_this_cycle >= MAX_TRADES_PER_CYCLE:
                break

            symbol = str(r["symbol"]).upper()
            venue = str(r.get("venue", "UNKNOWN")).upper()
            asset_class = str(r.get("asset_class", infer_asset_class(symbol, venue))).upper()
            price = safe_float(latest_prices.get(symbol, 0.0), 0.0)
            trade_score = safe_float(r.get("trade_score"), 0.0)
            signal_tier = str(r.get("signal_tier", "QUALIFIED")).upper()
            entry_quality_score = safe_float(r.get("entry_quality_score"), 0.0)

            if price <= 0.0:
                execution_audit.append(f"{symbol}: skipped_invalid_price")
                continue

            if position_manager.has_open_position(symbol):
                execution_audit.append(f"{symbol}: skipped_already_open")
                continue

            if in_reentry_cooldown(symbol, cycle):
                execution_audit.append(f"{symbol}: skipped_reentry_cooldown")
                continue

            if not capacity_available_for_asset_class(asset_class, open_counts):
                execution_audit.append(f"{symbol}: skipped_asset_cap_{asset_class}")
                continue

            eligible_after_asset_caps += 1

            trade_notional_usd = determine_trade_notional_usd(r)
            qty = trade_notional_usd / price

            position_manager.open_long_position(
                symbol=symbol,
                quantity=qty,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now(),
            )

            apply_post_open_overrides(
                symbol=symbol,
                price=price,
                signal_tier=signal_tier,
                asset_class=asset_class,
                venue=venue,
                entry_quality_score=entry_quality_score,
            )

            open_counts[asset_class] = open_counts.get(asset_class, 0) + 1
            open_counts["TOTAL"] = open_counts.get("TOTAL", 0) + 1

            opened_this_cycle += 1
            execution_audit.append(f"{symbol}: OPENED ({asset_class}/{venue})")

            print(
                f"[OPEN] {symbol} | venue={venue} | asset={asset_class} | "
                f"price={price:.6f} | qty={qty:.8f} | notional={trade_notional_usd:.2f} | "
                f"trade={trade_score:.2f} | tier={signal_tier} | "
                f"decision={str(r.get('decision', 'WATCH')).upper()} | "
                f"entryQ={entry_quality_score:.2f} | "
                f"liqQ={safe_float(r.get('liquidity_quality_score'), 0.0):.2f} | "
                f"junk={safe_float(r.get('junk_penalty_score'), 0.0):.2f} | "
                f"dirfit={safe_float(r.get('directional_long_fit'), 0.0):.2f} | "
                f"micro={safe_float(r.get('micro_trend_score'), 0.0):.2f} | "
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
            timestamp_utc=now(),
        )

        for trade in closed_positions:
            pnl = safe_float(trade.get("realized_pnl_usd"), 0.0)
            estimated_equity += pnl
            symbol = str(trade.get("symbol", "")).upper()
            if symbol:
                recent_exit_cycle_by_symbol[symbol] = cycle
            print(f"[CLOSE] {trade['symbol']} | reason={trade['exit_reason']} | pnl={pnl:.4f}")

        open_counts = count_open_positions_by_asset_class()
        pm_summary = position_manager.summary()

        summary = {
            "timestamp_utc": now(),
            "cycle_no": cycle,
            "engine_mode": ENGINE_MODE,
            "engine_profile": ACTIVE_PROFILE,
            "starting_capital_usd": starting_capital,
            "estimated_equity_usd": estimated_equity,
            "symbols_scanned": len(symbols),
            "signals_scanned": len(merged),
            "signals_passed_confluence": sum(
                1 for x in merged if x.get("confluence_allow_trade", False)
            ),
            "signals_passed_optimizer_gate": len(
                [x for x in merged if x.get("confluence_allow_trade", False) and passes_optimizer_gate(x, ACTIVE_PROFILE)]
            ),
            "signals_passed_execution_gate": len(
                [x for x in classified if passes_execution_gate(x, ACTIVE_PROFILE)]
            ),
            "signals_after_asset_caps": eligible_after_asset_caps,
            "opened_this_cycle": opened_this_cycle,
            "execution_audit": execution_audit,
            "max_symbols_per_cycle": MAX_SYMBOLS_PER_CYCLE,
            "max_trades_per_cycle": MAX_TRADES_PER_CYCLE,
            "max_open_positions_total": MAX_OPEN_POSITIONS_TOTAL,
            "max_open_positions_fx": MAX_OPEN_POSITIONS_FX,
            "max_open_positions_crypto": MAX_OPEN_POSITIONS_CRYPTO,
            "max_open_positions_other": MAX_OPEN_POSITIONS_OTHER,
            "reentry_cooldown_cycles": REENTRY_COOLDOWN_CYCLES,
            "base_trade_notional_usd": BASE_TRADE_NOTIONAL_USD,
            "elite_trade_notional_usd": ELITE_TRADE_NOTIONAL_USD,
            "qualified_trade_notional_usd": QUALIFIED_TRADE_NOTIONAL_USD,
            "watchlist_trade_notional_usd": WATCHLIST_TRADE_NOTIONAL_USD,
            "liquidity_quality_floor": LIQUIDITY_QUALITY_FLOOR,
            "junk_penalty_strict_floor": JUNK_PENALTY_STRICT_FLOOR,
            "open_fx": open_counts.get("FX", 0),
            "open_crypto": open_counts.get("CRYPTO", 0),
            "open_other": open_counts.get("OTHER", 0),
            "global_take_profit_pct": GLOBAL_TAKE_PROFIT_PCT,
            "global_stop_loss_pct": GLOBAL_STOP_LOSS_PCT,
            "global_max_hold_cycles": GLOBAL_MAX_HOLD_CYCLES,
            **pm_summary,
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
        print("Trade cap / total cap:", MAX_TRADES_PER_CYCLE, "/", MAX_OPEN_POSITIONS_TOTAL)
        print("Asset caps: FX=", MAX_OPEN_POSITIONS_FX, " CRYPTO=", MAX_OPEN_POSITIONS_CRYPTO, " OTHER=", MAX_OPEN_POSITIONS_OTHER, sep="")
        print("Open now: FX=", open_counts.get("FX", 0), " CRYPTO=", open_counts.get("CRYPTO", 0), " OTHER=", open_counts.get("OTHER", 0), sep="")
        print("TP/SL/Hold:", f"{GLOBAL_TAKE_PROFIT_PCT:.3f}", "/", f"{GLOBAL_STOP_LOSS_PCT:.3f}", "/", GLOBAL_MAX_HOLD_CYCLES)
        print("Execution style: CONDITION-DRIVEN / SESSION-LOCKED POLICY")
        print("Trades this cycle: top condition-qualified signals only")
        print("Signals passed final gate:", len([x for x in classified if passes_execution_gate(x, ACTIVE_PROFILE)]))
        print("Opened this cycle:", opened_this_cycle)
        print("Symbols:", symbols)

        print("\nAI SIGNAL SCANNER\n")
        if not classified:
            print("No optimized rows available this cycle.")
        else:
            for r in classified[:15]:
                exec_gate = "PASS" if passes_execution_gate(r, ACTIVE_PROFILE) else "HOLD"
                print(
                    f"{r['symbol']:10}"
                    f" venue={str(r.get('venue', 'UNKNOWN')).upper():10}"
                    f" asset={str(r.get('asset_class', 'OTHER')).upper():7}"
                    f" regime={str(r.get('regime', 'NEUTRAL')):12}"
                    f" tier={str(r.get('signal_tier', 'WATCH')).upper():10}"
                    f" decision={str(r.get('decision', 'WATCH')).upper():8}"
                    f" bias={str(r.get('micro_bias', 'NEUTRAL')).upper():7}"
                    f" base={safe_float(r.get('base_ai_score', 0.0)):.2f}"
                    f" score={safe_float(r.get('score'), 0.0):.2f}"
                    f" entryQ={safe_float(r.get('entry_quality_score'), 0.0):.2f}"
                    f" liqQ={safe_float(r.get('liquidity_quality_score'), 0.0):.2f}"
                    f" junk={safe_float(r.get('junk_penalty_score'), 0.0):.2f}"
                    f" dirfit={safe_float(r.get('directional_long_fit'), 0.0):.2f}"
                    f" pressure={safe_float(r.get('pressure_score'), 0.0):.2f}"
                    f" accel={safe_float(r.get('pressure_acceleration'), 0.0):.2f}"
                    f" micro={safe_float(r.get('micro_trend_score'), 0.0):.2f}"
                    f" vwap_dev={safe_float(r.get('vwap_dev_abs'), 0.0):.4f}"
                    f" rwin={safe_float(r.get('reversion_window_score'), 0.0):.2f}"
                    f" elas={safe_float(r.get('elasticity_score'), 0.0):.2f}"
                    f" confluence={safe_float(r.get('confluence_score'), 0.0):.2f}"
                    f" trade={safe_float(r.get('trade_score'), 0.0):.2f}"
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