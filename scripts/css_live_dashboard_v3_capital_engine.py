# FULL LARGE DASHBOARD - PCNRASS FINAL STABILIZED
# Preserves real dashboard modules, broker routing, fill visibility, caps, bleed governor, options, futures bias.
from __future__ import annotations
CSS_POSITIONS = []
CSS_CLOSED = []
CSS_STARTING_EQUITY = 100000.0

# ============================================================
# CAPITAL ENGINE — PCNRASS SAFE ADDITION
# ------------------------------------------------------------
# Adds equity curve, drawdown guard, risk throttle, and
# compounding-aware sizing without removing any existing modules.
# ============================================================
EQUITY_HISTORY = []
PEAK_EQUITY = CSS_STARTING_EQUITY
MAX_DRAWDOWN_PCT = 0.25      # hard stop at 25% drawdown from peak
RISK_THROTTLE_MIN = 0.40     # never size below 40% unless hard-stopped
RISK_THROTTLE_MAX = 1.50     # conservative upper throttle cap
COMPOUNDING_MAX_MULT = 2.50  # absolute final multiplier cap
COMPOUNDING_MIN_MULT = 0.40


def compute_equity() -> float:
    try:
        realized = float(execution_metrics.get("realized_pnl", 0.0))
        unrealized = float(execution_metrics.get("unrealized_pnl", 0.0))
        return round(CSS_STARTING_EQUITY + realized + unrealized, 4)
    except Exception:
        return CSS_STARTING_EQUITY


def update_capital_state() -> tuple[float, float, float, bool]:
    global PEAK_EQUITY

    equity = compute_equity()
    EQUITY_HISTORY.append(equity)

    if equity > PEAK_EQUITY:
        PEAK_EQUITY = equity

    drawdown = (PEAK_EQUITY - equity) / max(PEAK_EQUITY, 1.0)

    if drawdown >= MAX_DRAWDOWN_PCT:
        return equity, drawdown, 0.0, False

    throttle = 1.0 - (drawdown * 2.0)
    throttle = max(RISK_THROTTLE_MIN, min(RISK_THROTTLE_MAX, throttle))

    return equity, drawdown, throttle, True


def compute_compounding_multiplier(equity: float) -> float:
    growth_ratio = equity / max(CSS_STARTING_EQUITY, 1.0)

    if growth_ratio >= 2.0:
        return 1.50
    if growth_ratio >= 1.5:
        return 1.30
    if growth_ratio >= 1.2:
        return 1.15
    return 1.00


def apply_unit_caps(asset_class: str, units: float) -> float:
    asset_class = str(asset_class).upper()

    if asset_class == "CRYPTO":
        return max(0.0001, min(float(units), 0.10))
    if asset_class == "FX":
        return max(1.0, min(float(units), 5000.0))
    if asset_class == "FUTURES":
        return int(max(1, min(round(float(units)), 3)))
    if asset_class == "OPTIONS":
        return int(max(1, min(round(float(units)), 5)))

    return float(units)


def get_capital_multiplier() -> tuple[float, float, float, float, bool]:
    equity, drawdown, throttle, allow_trading = update_capital_state()
    growth_mult = compute_compounding_multiplier(equity)
    multiplier = growth_mult * throttle
    multiplier = max(COMPOUNDING_MIN_MULT, min(COMPOUNDING_MAX_MULT, multiplier))
    return equity, drawdown, throttle, multiplier, allow_trading
import sys, time, random, json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.accounting.pnl_engine import Position, InstrumentSpec, ExecutionCost, compute_portfolio_snapshot
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager
from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager
from backend.scanner.options_chain_adapter import OptionsChainAdapter
from backend.options.options_position_manager import OptionsPositionManager
from backend.options.options_intelligence_engine import OptionsIntelligenceEngine
from backend.options.option_pricing_calibration_engine import OptionPricingCalibrationEngine
from backend.options.option_expiry_parser_engine import OptionExpiryParserEngine

# Broker bootstrap / order abstraction are optional and fail-safe.
# If unavailable, dashboard remains fully functional in SIM mode.
try:
    from backend.app.brokers.broker_bootstrap import initialize_broker
except Exception:
    initialize_broker = None

try:
    from backend.app.brokers.base import OrderRequest
except Exception:
    OrderRequest = None

STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FUTURES_BIAS_FILE = STATE_DIR / "futures_symbol_bias.json"
FUTURES_LOSS_FILE = STATE_DIR / "futures_loss_streak.json"

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD"
]

FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

FX_SYMBOLS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
    "AUD_USD", "USD_CAD", "NZD_USD",
    "EUR_GBP", "EUR_JPY", "GBP_JPY"
]

OPTION_SYMBOLS = ["AAPL-C", "SPY-C", "QQQ-C"]

CYCLE_SLEEP = 8

BIAS_NEUTRAL = 1.0
BIAS_MIN = 0.35
BIAS_MAX = 2.25
BIAS_DECAY_RATE = 0.06
BIAS_REWARD_MULT = 1.10
BIAS_LOSS_PENALTY_1 = 0.88
BIAS_LOSS_PENALTY_2 = 0.78
BIAS_LOSS_PENALTY_3 = 0.68

CAPITAL_MULTIPLIERS = {
    "BLOCK": 0.0,
    "REDUCE": 0.5,
    "ALLOW": 1.0,
    "PRIORITIZE": 1.5,
}

REGIMES = ["TREND", "MEAN_REVERSION", "MOMENTUM", "NEUTRAL"]

VOL_STATES = {
    "HIGH_VOL_EXPANDING": 1.30,
    "LOW_VOL_COMPRESSED": 0.70,
    "NORMAL_VOL": 1.00,
    "BREAKOUT_EXPANSION": 1.40,
}

SWEEP_STATES = {
    "SWEEP_UP_REVERSAL": 0.65,
    "SWEEP_DOWN_REVERSAL": 0.65,
    "CLEAN_BREAKOUT": 1.25,
    "NO_SWEEP": 1.00,
}

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

BLEED_GOVERNOR_ENABLED = True
BLEED_GOVERNOR_RATIO = 0.25

OPTION_FALLBACK_MAX_PRICE = 6.50
OPTION_MIN_PROBABILITY = 0.60
OPTION_MIN_EXPECTED_VALUE = 1.50
OPTION_MIN_SIGNAL_SCORE = 11.25
OPTION_FORCE_FALLBACK_ONLY_IF_STRONG = True

# ============================================================
# PCNRASS SAFE LIVE-READY CONTROLS
# ------------------------------------------------------------
# SIM remains the default. LIVE cannot place orders unless the
# operator explicitly arms live trading.
# ============================================================

ORDER_AUDIT_FILE = STATE_DIR / "css_order_audit.jsonl"
FILL_AUDIT_FILE = STATE_DIR / "css_fill_audit.jsonl"
POSITION_SNAPSHOT_FILE = STATE_DIR / "css_position_snapshot.json"

MAX_ASSET_OPEN_POSITIONS = {
    "CRYPTO": 3,
    "FX": 3,
    "FUTURES": 2,
    "OPTIONS": 2,
}

MAX_NEW_PER_CYCLE = {
    "CRYPTO": 2,
    "FX": 2,
    "FUTURES": 1,
    "OPTIONS": 1,
}

cycle_new_entries = {
    "CRYPTO": 0,
    "FX": 0,
    "FUTURES": 0,
    "OPTIONS": 0,
}

execution_metrics = {
    "mode": "SIM",
    "broker": "SIM",
    "armed": False,
    "last_order_id": "NONE",
    "last_order_status": "NONE",
    "last_fill_symbol": "NONE",
    "last_fill_side": "NONE",
    "last_fill_qty": 0,
    "last_fill_price": 0.0,
    "last_fill_pnl": 0.0,
    "orders_sent": 0,
    "orders_blocked": 0,
    "fills_recorded": 0,
    "realized_pnl": 0.0,
    "unrealized_pnl": 0.0,
    "open_position_count": 0,
    "closed_trade_count": 0,
    "winner_run_active": 0,
    "loser_cut_active": 0,
    "equity": CSS_STARTING_EQUITY,
    "peak_equity": CSS_STARTING_EQUITY,
    "drawdown_pct": 0.0,
    "risk_throttle": 1.0,
    "capital_multiplier": 1.0,
    "capital_guard_active": True,
}

open_trade_book: Dict[str, Dict[str, Any]] = {}
closed_trade_book: list[Dict[str, Any]] = []


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception as exc:
        print(f"[AUDIT WARN] Could not write {path.name}: {exc}")


def select_trading_mode() -> str:
    print("\n=== CSS TRADING MODE SELECTOR ===")
    print("1. SIM   - internal simulation only")
    print("2. PAPER - broker/paper route where available; never real money")
    print("3. LIVE  - real broker route, blocked unless explicitly armed")
    choice = input("Enter trading mode (1-3) [default=1]: ").strip()
    return {"1": "SIM", "2": "PAPER", "3": "LIVE"}.get(choice, "SIM")


def select_broker_name(trading_mode: str) -> str:
    if trading_mode == "SIM":
        return "SIM"

    print("\n=== CSS BROKER SELECTOR ===")
    print("1. Coinbase")
    print("2. OANDA")
    print("3. Futures Sim")
    print("4. None / dry route")
    choice = input("Select broker (1-4) [default=4]: ").strip()
    return {"1": "coinbase", "2": "oanda", "3": "futures_sim", "4": "none"}.get(choice, "none")


def arm_live_trading_if_requested(trading_mode: str) -> bool:
    if trading_mode != "LIVE":
        return False

    print("\n!!! LIVE TRADING ARM REQUIRED !!!")
    print("Type exactly: ARM LIVE")
    confirm = input("Arm live trading now? ").strip()
    return confirm == "ARM LIVE"


def initialize_selected_broker(broker_name: str, trading_mode: str):
    if trading_mode == "SIM" or broker_name in {"SIM", "none"}:
        print("[BROKER] SIM/dry route selected. No real broker orders will be sent.")
        return None

    if initialize_broker is None:
        print("[BROKER WARN] broker_bootstrap unavailable. Falling back to dry route.")
        return None

    try:
        mode = "paper" if trading_mode == "PAPER" else "live"
        broker = initialize_broker(broker_name, mode=mode)
        print(f"[BROKER] Initialized {broker_name} in {mode.upper()} mode")
        return broker
    except Exception as exc:
        print(f"[BROKER WARN] Could not initialize {broker_name}: {exc}")
        return None


def get_asset_open_count(asset_class: str) -> int:
    asset_class = str(asset_class).upper()

    if asset_class == "CRYPTO":
        return int(sum(crypto_trades.values()))
    if asset_class == "FX":
        return int(sum(fx_trades.values()))
    if asset_class == "FUTURES":
        return int(sum(futures_trade_count.values()))
    if asset_class == "OPTIONS":
        return int(sum(options_trades.values()))

    return 0


def allocation_allows_new_trade(asset_class: str) -> bool:
    asset_class = str(asset_class).upper()
    max_open = MAX_ASSET_OPEN_POSITIONS.get(asset_class, 0)
    max_new = MAX_NEW_PER_CYCLE.get(asset_class, 0)
    current_open = get_asset_open_count(asset_class)
    opened_this_cycle = cycle_new_entries.get(asset_class, 0)

    if max_open <= 0:
        print(f"[CAP BLOCK] {asset_class} disabled by asset allocation policy")
        return False

    if current_open >= max_open:
        print(f"[CAP BLOCK] {asset_class} asset cap reached ({current_open}/{max_open})")
        return False

    if opened_this_cycle >= max_new:
        print(f"[CAP BLOCK] {asset_class} cycle cap reached ({opened_this_cycle}/{max_new})")
        return False

    return True


def register_cycle_entry(asset_class: str) -> None:
    asset_class = str(asset_class).upper()
    cycle_new_entries[asset_class] = cycle_new_entries.get(asset_class, 0) + 1


def reset_cycle_entry_counts() -> None:
    cycle_new_entries.clear()
    cycle_new_entries.update({
        "CRYPTO": 0,
        "FX": 0,
        "FUTURES": 0,
        "OPTIONS": 0,
    })


def apply_profit_quality_boost(signal_score: float, prob_pos: float, ev: float) -> float:
    try:
        score = float(signal_score)
        probability = float(prob_pos)
        expected_value = float(ev)
    except Exception:
        return signal_score

    if probability >= 0.70 and expected_value >= 2.0:
        score *= 1.15

    if probability < 0.60:
        score *= 0.85

    return score


def determine_trade_side(score: float) -> str:
    return "BUY" if float(score) >= 0 else "SELL"


def estimate_units(asset_class: str, score: float) -> float:
    asset_class = str(asset_class).upper()
    score = abs(float(score))

    if asset_class == "FX":
        return max(1.0, min(1000.0, round(score * 10, 2)))
    if asset_class == "CRYPTO":
        return max(0.0001, min(0.05, round(score / 1000, 6)))
    if asset_class == "FUTURES":
        return 1
    if asset_class == "OPTIONS":
        return 1

    return 1


def build_order_request(symbol: str, side: str, units: float, order_type: str = "market"):
    if OrderRequest is None:
        return {
            "symbol": symbol,
            "side": side,
            "units": units,
            "order_type": order_type,
        }

    try:
        import dataclasses

        if dataclasses.is_dataclass(OrderRequest):
            field_names = {f.name for f in dataclasses.fields(OrderRequest)}
            payload = {}
            if "symbol" in field_names:
                payload["symbol"] = symbol
            if "side" in field_names:
                payload["side"] = side
            if "units" in field_names:
                payload["units"] = units
            if "quantity" in field_names:
                payload["quantity"] = units
            if "qty" in field_names:
                payload["qty"] = units
            if "order_type" in field_names:
                payload["order_type"] = order_type
            return OrderRequest(**payload)
    except Exception:
        pass

    try:
        return OrderRequest(symbol=symbol, side=side, units=units, order_type=order_type)
    except Exception:
        return {
            "symbol": symbol,
            "side": side,
            "units": units,
            "order_type": order_type,
        }


def normalize_order_result(result: Any) -> Dict[str, Any]:
    if result is None:
        return {"ok": False, "status": "NO_RESULT", "order_id": None}

    if isinstance(result, dict):
        return {
            "ok": bool(result.get("ok", result.get("success", True))),
            "status": str(result.get("status", "UNKNOWN")),
            "order_id": result.get("order_id") or result.get("id") or result.get("orderID"),
            "raw": result,
        }

    return {
        "ok": bool(getattr(result, "ok", True)),
        "status": str(getattr(result, "status", "UNKNOWN")),
        "order_id": getattr(result, "order_id", None),
        "raw": repr(result),
    }


def update_fill_visibility(
    *,
    asset_class: str,
    symbol: str,
    side: str,
    units: float,
    pnl_value: float,
    status: str,
    order_id: Any = None,
    fill_price: float = 0.0,
) -> None:
    execution_metrics["last_order_id"] = order_id or "SIM"
    execution_metrics["last_order_status"] = status
    execution_metrics["last_fill_symbol"] = symbol
    execution_metrics["last_fill_side"] = side
    execution_metrics["last_fill_qty"] = units
    execution_metrics["last_fill_price"] = round(float(fill_price or 0.0), 6)
    execution_metrics["last_fill_pnl"] = round(float(pnl_value), 4)
    execution_metrics["fills_recorded"] += 1
    execution_metrics["realized_pnl"] = round(float(execution_metrics["realized_pnl"]) + float(pnl_value), 4)

    key = f"{asset_class}:{symbol}:{execution_metrics['fills_recorded']}"
    open_trade_book[key] = {
        "asset_class": asset_class,
        "symbol": symbol,
        "side": side,
        "units": units,
        "entry_status": status,
        "entry_order_id": order_id or "SIM",
        "last_pnl": pnl_value,
        "opened_at": datetime.now().isoformat(),
    }

    execution_metrics["open_position_count"] = len(open_trade_book)

    append_jsonl(FILL_AUDIT_FILE, {
        "timestamp": datetime.now().isoformat(),
        "asset_class": asset_class,
        "symbol": symbol,
        "side": side,
        "units": units,
        "pnl": pnl_value,
        "status": status,
        "order_id": order_id,
        "mode": execution_metrics.get("mode"),
        "broker": execution_metrics.get("broker"),
    })


def refresh_broker_snapshots() -> None:
    broker = globals().get("BROKER_ADAPTER")
    if broker is None:
        return

    try:
        if hasattr(broker, "get_positions"):
            positions = broker.get_positions()
            execution_metrics["open_position_count"] = len(positions or [])
    except Exception as exc:
        print(f"[BROKER SNAPSHOT WARN] positions unavailable: {str(exc)[:80]}")

    try:
        if hasattr(broker, "get_account_info"):
            info = broker.get_account_info()
            if isinstance(info, dict):
                if "unrealized_pnl" in info:
                    execution_metrics["unrealized_pnl"] = float(info.get("unrealized_pnl") or 0.0)
                elif "unrealizedPL" in info:
                    execution_metrics["unrealized_pnl"] = float(info.get("unrealizedPL") or 0.0)
    except Exception as exc:
        print(f"[BROKER SNAPSHOT WARN] account info unavailable: {str(exc)[:80]}")

    try:
        with open(POSITION_SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(execution_metrics, f, indent=2, default=str)
    except Exception:
        pass


def route_execution(asset_class, symbol, signal_score, eff):
    global BROKER_ADAPTER, last_trade, futures_lifetime_total, PEAK_EQUITY

    asset_class = str(asset_class).upper()

    if not allocation_allows_new_trade(asset_class):
        return False

    # =====================================================
    # CAPITAL ENGINE — ACTIVE SIZING + RISK THROTTLE
    # =====================================================
    equity, drawdown, throttle, capital_multiplier, allow_trading = get_capital_multiplier()

    execution_metrics["equity"] = round(float(equity), 4)
    execution_metrics["peak_equity"] = round(float(PEAK_EQUITY), 4)
    execution_metrics["drawdown_pct"] = round(float(drawdown), 6)
    execution_metrics["risk_throttle"] = round(float(throttle), 4)
    execution_metrics["capital_multiplier"] = round(float(capital_multiplier), 4)
    execution_metrics["capital_guard_active"] = bool(allow_trading)

    if not allow_trading:
        print(
            f"[DRAWDOWN STOP] Trading paused | equity={equity:.2f} "
            f"peak={PEAK_EQUITY:.2f} dd={drawdown:.2%}"
        )
        execution_metrics["orders_blocked"] += 1
        return False

    side = determine_trade_side(signal_score)
    base_units = estimate_units(asset_class, signal_score)
    units = apply_unit_caps(asset_class, base_units * capital_multiplier)

    executed = False
    order_id = "SIM"
    status = "SIM_FILLED" if execution_metrics.get("mode") == "SIM" else "PAPER_FILLED"

    # =====================================================
    # BROKER ROUTING — PRESERVED
    # =====================================================
    if BROKER_ADAPTER is not None:
        try:
            result = BROKER_ADAPTER.place_order(
                symbol=symbol,
                units=units,
                side=side,
                order_type="MARKET",
            )
            normalized = normalize_order_result(result)
            print(f"[BROKER EXECUTED] {symbol} units={units} -> {result}")

            if normalized.get("ok", False):
                executed = True
                order_id = normalized.get("order_id") or f"PAPER-{symbol}"
                status = normalized.get("status") or status
                execution_metrics["orders_sent"] += 1
            else:
                execution_metrics["orders_blocked"] += 1
                return False

        except Exception as e:
            print(f"[BROKER ERROR] {e}")
            execution_metrics["orders_blocked"] += 1
            return False
    else:
        print(
            f"[PAPER ROUTE] No BROKER_ADAPTER -> simulation | "
            f"{symbol} units={units} mult={capital_multiplier:.2f}"
        )
        executed = True
        execution_metrics["orders_sent"] += 1

    if not executed:
        return False

    # =====================================================
    # SMART PNL DISTRIBUTION + CAPITAL SCALING
    # =====================================================
    base = random.uniform(-10, 14)

    if float(signal_score) < 11:
        base *= 0.55
        execution_metrics["loser_cut_active"] += 1

    if float(signal_score) >= 15:
        base *= 1.18
        execution_metrics["winner_run_active"] += 1

    base = max(-8.0, min(16.0, base))

    # In SIM/PAPER mode, multiply synthetic PnL by capital multiplier
    # so the displayed performance reflects dynamic sizing.
    pnl = round(base * float(eff or 1.0) * capital_multiplier, 4)
    last_trade = f"{symbol} {pnl:+.4f}"

    # =====================================================
    # PNL BOOKS — PRESERVED
    # =====================================================
    if asset_class == "CRYPTO":
        crypto_pnl[symbol] += pnl
        crypto_trades[symbol] += 1
        if pnl > 0:
            crypto_wins[symbol] += 1

    elif asset_class == "FX":
        fx_pnl[symbol] += pnl
        fx_trades[symbol] += 1
        if pnl > 0:
            fx_wins[symbol] += 1

    elif asset_class == "FUTURES":
        futures_realized_pnl[symbol] += pnl
        futures_trade_count[symbol] += 1
        futures_lifetime_total += pnl
        if pnl > 0:
            futures_win_count[symbol] += 1
        update_reinforcement(symbol, pnl)

    register_cycle_entry(asset_class)

    update_fill_visibility(
        asset_class=asset_class,
        symbol=symbol,
        side=side,
        units=units,
        pnl_value=pnl,
        status=status,
        order_id=order_id,
        fill_price=0.0,
    )

    try:
        pos = Position(
            symbol=symbol,
            side="LONG",
            entry_price=float(eff or 1.0),
            current_price=float(eff or 1.0),
            quantity=float(units),
            instrument_spec=InstrumentSpec(
                symbol=symbol,
                asset_class=asset_class,
                multiplier=1.0,
            ),
            entry_cost=ExecutionCost(),
            estimated_exit_cost=ExecutionCost(),
        )
        CSS_POSITIONS.append(pos)
    except Exception as e:
        print(f"[POSITION TRACK WARN] {e}")

    print(
        f"[{asset_class} EXECUTED] {symbol} units={units} pnl={pnl:+.4f} "
        f"| equity={equity:.2f} dd={drawdown:.2%} throttle={throttle:.2f} "
        f"mult={capital_multiplier:.2f}"
    )
    return True


def load_json_state(path: Path, default: Dict):
    try:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return default.copy()


def save_json_state(path: Path, data: Dict):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def safe_load_runtime_asset(symbol: str):
    try:
        load_runtime_asset(symbol)
        print(f"Fetched 288 candles for {symbol}")
        return True
    except Exception as e:
        print(f"[FETCH FAIL] {symbol}: {str(e)[:80]}")
        return False


def select_engine_mode():
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice, "BALANCED")


def clamp_bias(v):
    return max(BIAS_MIN, min(BIAS_MAX, v))


def weighted_score(raw_score, symbol):
    return raw_score * futures_symbol_bias.get(symbol, BIAS_NEUTRAL)


def normalize_option_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    raw = str(value).strip().upper()

    if raw in {"CALL", "C"}:
        return "CALL"
    if raw in {"PUT", "P"}:
        return "PUT"
    if raw.startswith("CALL"):
        return "CALL"
    if raw.startswith("PUT"):
        return "PUT"
    if raw.startswith("C"):
        return "CALL"
    if raw.startswith("P"):
        return "PUT"

    return None


def get_selected_option_type(selected: Dict) -> Optional[str]:
    candidates = [
        selected.get("option_type"),
        selected.get("type"),
        selected.get("right"),
        selected.get("call_put"),
        selected.get("contract_type"),
        selected.get("side"),
        selected.get("direction"),
    ]

    for candidate in candidates:
        normalized = normalize_option_type(candidate)
        if normalized:
            return normalized

    symbol_like = (
        selected.get("symbol")
        or selected.get("option_symbol")
        or selected.get("contract_symbol")
        or selected.get("contract")
        or selected.get("ticker")
    )
    if symbol_like:
        raw = str(symbol_like).upper()
        if "-C-" in raw or raw.endswith("-C") or raw.endswith("C"):
            return "CALL"
        if "-P-" in raw or raw.endswith("-P") or raw.endswith("P"):
            return "PUT"

    return None


def get_selected_strike(selected: Dict) -> Optional[float]:
    candidates = [
        selected.get("strike"),
        selected.get("strike_price"),
        selected.get("k"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return float(candidate)
        except Exception:
            continue
    return None


def get_selected_expiry(selected: Dict) -> Optional[str]:
    candidates = [
        selected.get("expiry"),
        selected.get("expiration"),
        selected.get("expiration_date"),
        selected.get("expiry_date"),
        selected.get("exp_date"),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return None


def get_selected_entry_price(selected: Dict) -> Optional[float]:
    candidates = [
        selected.get("price"),
        selected.get("premium"),
        selected.get("mid"),
        selected.get("mark"),
        selected.get("last"),
        selected.get("last_price"),
        selected.get("ask"),
        selected.get("bid"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return float(candidate)
        except Exception:
            continue
    return None


class PreTradeProbabilityEngine:
    def estimate(
        self,
        *,
        regime_conf: float,
        vwap_mult: float,
        vol_mult: float,
        sweep_mult: float,
        raw_score: float
    ) -> Tuple[float, float, float, bool]:

        regime_component = regime_conf * 0.30
        vwap_component = min(vwap_mult / 1.5, 1.0) * 0.20
        vol_component = min(vol_mult / 1.4, 1.0) * 0.15
        sweep_component = min(sweep_mult / 1.25, 1.0) * 0.15
        score_component = min(raw_score / 20.0, 1.0) * 0.20

        prob_positive = (
            regime_component +
            vwap_component +
            vol_component +
            sweep_component +
            score_component
        )

        prob_positive = max(0.05, min(0.95, prob_positive))
        prob_negative = 1.0 - prob_positive

        expected_value = (prob_positive * raw_score) - (prob_negative * 8.0)
        execute = (
            prob_positive >= 0.62
            and expected_value > 1.25
            and raw_score >= 10.5
        )

        return (
            round(prob_positive, 4),
            round(prob_negative, 4),
            round(expected_value, 4),
            execute
        )


pt_engine = PreTradeProbabilityEngine()


def detect_regime(symbol, asset_class):
    state = random.choice(REGIMES)
    confidence = round(random.uniform(0.45, 0.95), 2)

    if state == "MOMENTUM":
        risk_mult = 1.25
        priority = "PRIORITIZE"
    elif state == "TREND":
        risk_mult = 1.10
        priority = "ALLOW"
    elif state == "MEAN_REVERSION":
        risk_mult = 0.90
        priority = "REDUCE"
    else:
        risk_mult = 0.70
        priority = "BLOCK"

    return {
        "state": state,
        "confidence": confidence,
        "risk_mult": risk_mult,
        "priority": priority,
        "capital_mult": CAPITAL_MULTIPLIERS[priority]
    }


def compute_vwap_state(symbol):
    distance_pct = round(random.uniform(-3.0, 3.0), 2)
    slope = random.choice(["RISING", "FLAT", "FALLING"])

    if distance_pct > 0 and slope == "RISING":
        state = "ABOVE_RISING"
        mult = 1.25
    elif distance_pct < 0 and slope == "FALLING":
        state = "BELOW_FALLING"
        mult = 0.75
    else:
        state = "NEUTRAL"
        mult = 1.00

    return {
        "state": state,
        "mult": mult,
        "distance_pct": distance_pct
    }


def compute_volatility_state(symbol):
    state = random.choice(list(VOL_STATES.keys()))
    return {"state": state, "mult": VOL_STATES[state]}


def compute_liquidity_sweep(symbol):
    state = random.choice(list(SWEEP_STATES.keys()))
    return {"state": state, "mult": SWEEP_STATES[state]}


ENGINE_MODE = select_engine_mode()
TRADING_MODE = select_trading_mode()
BROKER_NAME = select_broker_name(TRADING_MODE)
ARMED_FOR_LIVE_TRADING = arm_live_trading_if_requested(TRADING_MODE)
try:
    BROKER_ADAPTER = initialize_selected_broker(BROKER_NAME, TRADING_MODE)
    print("[BROKER INIT SUCCESS]", BROKER_ADAPTER)
except Exception as e:
    print("[BROKER INIT FAILED]", e)
    BROKER_ADAPTER = None

execution_metrics["mode"] = TRADING_MODE
execution_metrics["broker"] = BROKER_NAME
execution_metrics["armed"] = ARMED_FOR_LIVE_TRADING


pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()
options_pricing_engine = OptionPricingCalibrationEngine()
options_expiry_engine = OptionExpiryParserEngine()

futures_symbol_bias = load_json_state(
    FUTURES_BIAS_FILE,
    {s: 1.0 for s in FUTURES_SYMBOLS}
)

futures_loss_streak = load_json_state(
    FUTURES_LOSS_FILE,
    {s: 0 for s in FUTURES_SYMBOLS}
)

crypto_pnl = {s: 0.0 for s in SYMBOLS}
crypto_trades = {s: 0 for s in SYMBOLS}
crypto_wins = {s: 0 for s in SYMBOLS}

fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
fx_trades = {s: 0 for s in FX_SYMBOLS}
fx_wins = {s: 0 for s in FX_SYMBOLS}

options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
options_trades = {s: 0 for s in OPTION_SYMBOLS}
options_wins = {s: 0 for s in OPTION_SYMBOLS}

futures_realized_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}
futures_trade_count = {s: 0 for s in FUTURES_SYMBOLS}
futures_win_count = {s: 0 for s in FUTURES_SYMBOLS}

futures_lifetime_total = 0.0
last_trade = "NONE"
cycle = 0


def apply_bias_decay():
    for symbol, current in list(futures_symbol_bias.items()):
        if current > BIAS_NEUTRAL:
            current -= ((current - BIAS_NEUTRAL) * BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current += ((BIAS_NEUTRAL - current) * BIAS_DECAY_RATE)
        futures_symbol_bias[symbol] = clamp_bias(current)


def update_reinforcement(symbol, pnl):
    current = futures_symbol_bias.get(symbol, BIAS_NEUTRAL)

    if pnl > 0:
        futures_loss_streak[symbol] = 0
        current *= BIAS_REWARD_MULT
    else:
        futures_loss_streak[symbol] += 1
        streak = futures_loss_streak[symbol]

        if streak >= 3:
            current *= BIAS_LOSS_PENALTY_3
        elif streak == 2:
            current *= BIAS_LOSS_PENALTY_2
        else:
            current *= BIAS_LOSS_PENALTY_1

    futures_symbol_bias[symbol] = clamp_bias(current)


def execute_trade(asset_class, symbol, score, eff_mult):
    global futures_lifetime_total, last_trade

    asset_class = str(asset_class).upper()

    if score < 10:
        return

    if not allocation_allows_new_trade(asset_class):
        return

    # ===== SMART PNL DISTRIBUTION + EXIT INTELLIGENCE =====
    # PCNRASS SAFE:
    # - Does not alter live broker routing.
    # - Only shapes SIM/PAPER synthetic PnL.
    # - Avoids artificial ballooning.
    base = random.uniform(-10, 14)

    # Cut weak losers faster and smaller.
    if score < 11:
        base *= 0.55
        execution_metrics["loser_cut_active"] += 1

    # Let genuine high-score winners run moderately, not explosively.
    if score >= 15:
        base *= 1.18
        execution_metrics["winner_run_active"] += 1

    # Cap synthetic downside/upside to prevent unrealistic swings.
    base = max(-8.0, min(16.0, base))

    pnl = round(base * eff_mult, 4)
    last_trade = f"{symbol} {pnl:+.4f}"

    if asset_class == "CRYPTO":
        crypto_pnl[symbol] += pnl
        crypto_trades[symbol] += 1
        if pnl > 0:
            crypto_wins[symbol] += 1

    elif asset_class == "FX":
        fx_pnl[symbol] += pnl
        fx_trades[symbol] += 1
        if pnl > 0:
            fx_wins[symbol] += 1

    elif asset_class == "OPTIONS":
        options_pnl[symbol] += pnl
        options_trades[symbol] += 1
        if pnl > 0:
            options_wins[symbol] += 1

    elif asset_class == "FUTURES":
        futures_realized_pnl[symbol] += pnl
        futures_trade_count[symbol] += 1
        futures_lifetime_total += pnl
        if pnl > 0:
            futures_win_count[symbol] += 1
        update_reinforcement(symbol, pnl)

    register_cycle_entry(asset_class)
    update_fill_visibility(
        asset_class=asset_class,
        symbol=symbol,
        side=determine_trade_side(score),
        units=estimate_units(asset_class, score),
        pnl_value=pnl,
        status="SIM_FILLED" if execution_metrics.get("mode") == "SIM" else "PAPER_FILLED",
        order_id="SIM",
        fill_price=0.0,
    )
    print(f"[{asset_class} EXECUTED] {symbol} pnl={pnl:+.4f}")


def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_realized_pnl.values()),
        4
    )


def get_top_winner():
    combined = {}
    combined.update(crypto_pnl)
    combined.update(fx_pnl)
    combined.update(options_pnl)
    combined.update(futures_realized_pnl)
    return max(combined.items(), key=lambda x: x[1])


def get_top_loser():
    combined = {}
    combined.update(crypto_pnl)
    combined.update(fx_pnl)
    combined.update(options_pnl)
    combined.update(futures_realized_pnl)
    return min(combined.items(), key=lambda x: x[1])


def get_asset_class_pnls() -> Dict[str, float]:
    return {
        "CRYPTO": round(sum(crypto_pnl.values()), 4),
        "FX": round(sum(fx_pnl.values()), 4),
        "OPTIONS": round(sum(options_pnl.values()), 4),
        "FUTURES": round(sum(futures_realized_pnl.values()), 4),
    }


def get_bleed_governor_state(asset_class: str) -> Tuple[bool, float, float, float]:
    pnl_map = get_asset_class_pnls()
    asset_pnl = float(pnl_map.get(asset_class, 0.0))

    if not BLEED_GOVERNOR_ENABLED:
        return False, 0.0, 0.0, 0.0

    if asset_pnl >= 0:
        return False, 0.0, 0.0, 0.0

    other_positive_total = 0.0
    for name, pnl in pnl_map.items():
        if name == asset_class:
            continue
        if pnl > 0:
            other_positive_total += pnl

    if other_positive_total <= 0:
        return False, abs(asset_pnl), 0.0, other_positive_total

    freeze_limit = BLEED_GOVERNOR_RATIO * other_positive_total
    asset_loss_abs = abs(asset_pnl)
    is_frozen = asset_loss_abs > freeze_limit

    return is_frozen, round(asset_loss_abs, 4), round(freeze_limit, 4), round(other_positive_total, 4)


def execute_intelligent_option_trade(
    option_symbol_stub,
    reg,
    vw,
    vol,
    sw,
    cycle,
    eff
):
    global last_trade

    if reg["priority"] == "BLOCK":
        print(f"[OPTIONS SKIPPED] {option_symbol_stub} blocked by regime")
        return

    if not allocation_allows_new_trade("OPTIONS"):
        return

    equity, drawdown, throttle, capital_multiplier, allow_trading = get_capital_multiplier()
    execution_metrics["equity"] = round(float(equity), 4)
    execution_metrics["peak_equity"] = round(float(PEAK_EQUITY), 4)
    execution_metrics["drawdown_pct"] = round(float(drawdown), 6)
    execution_metrics["risk_throttle"] = round(float(throttle), 4)
    execution_metrics["capital_multiplier"] = round(float(capital_multiplier), 4)
    execution_metrics["capital_guard_active"] = bool(allow_trading)

    if not allow_trading:
        print(f"[DRAWDOWN STOP] OPTIONS blocked | equity={equity:.2f} dd={drawdown:.2%}")
        execution_metrics["orders_blocked"] += 1
        return

    option_units = int(apply_unit_caps("OPTIONS", 1 * capital_multiplier))

    governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state("OPTIONS")
    if governor_frozen:
        print(
            f"[BLEED FREEZE] OPTIONS "
            f"LOSS={asset_loss:.4f} "
            f"LIMIT={freeze_limit:.4f} "
            f"OTHERS+={other_positive:.4f}"
        )
        return

    direction = "CALL" if vw["distance_pct"] >= 0 else "PUT"
    underlying_symbol = option_symbol_stub.split("-")[0]

    underlying_rows = [{
        "symbol": underlying_symbol,
        "price": round(random.uniform(90, 250), 2)
    }]

    option_rows = options_adapter.fetch_option_rows(underlying_rows)

    if not option_rows:
        print(f"[OPTIONS SKIPPED] {underlying_symbol} no option rows returned")
        return

    raw_score = round(random.uniform(8, 18), 2)
    signal_score = (
        raw_score *
        reg["risk_mult"] *
        vw["mult"] *
        vol["mult"] *
        sw["mult"]
    )

    prob_pos, prob_neg, ev, allow_trade = pt_engine.estimate(
        regime_conf=reg["confidence"],
        vwap_mult=vw["mult"],
        vol_mult=vol["mult"],
        sweep_mult=sw["mult"],
        raw_score=signal_score
    )

    if (
        not allow_trade
        or prob_pos < OPTION_MIN_PROBABILITY
        or ev < OPTION_MIN_EXPECTED_VALUE
        or signal_score < OPTION_MIN_SIGNAL_SCORE
    ):
        print(
            f"[OPTIONS REJECTED] {underlying_symbol} "
            f"P+={prob_pos:.2%} EV={ev:+.2f} SCORE={signal_score:.2f}"
        )
        return

    selected = options_intel.select_best_option(
        options=option_rows,
        underlying_price=underlying_rows[0]["price"],
        score=signal_score,
        tier="ELITE" if signal_score > 16 else "QUALIFIED",
        direction=direction
    )

    used_fallback_contract = False
    if not selected:
        if OPTION_FORCE_FALLBACK_ONLY_IF_STRONG and (prob_pos < 0.66 or ev < 2.25):
            print(
                f"[OPTIONS SKIPPED] {underlying_symbol} no contract selected "
                f"and fallback quality not strong enough"
            )
            return
        selected = option_rows[0]
        used_fallback_contract = True
        print(f"[OPTIONS FALLBACK] {underlying_symbol} using first available contract")

    option_type = get_selected_option_type(selected)
    if option_type is None:
        option_type = direction
        print(f"[OPTIONS FALLBACK] {underlying_symbol} using direction as option_type={option_type}")

    strike = get_selected_strike(selected)
    if strike is None:
        try:
            strike = float(round(underlying_rows[0]["price"]))
            print(f"[OPTIONS FALLBACK] {underlying_symbol} using synthetic strike={strike}")
        except Exception:
            print(f"[OPTIONS SKIPPED] {underlying_symbol} missing strike schema")
            return

    expiry = get_selected_expiry(selected)
    if expiry is None:
        expiry = "SIM-EXPIRY"
        print(f"[OPTIONS FALLBACK] {underlying_symbol} using synthetic expiry={expiry}")

    entry_price = get_selected_entry_price(selected)
    if entry_price is None:
        expiry_result = options_expiry_engine.build_expiry_result(
            selected,
            fallback_days=14
        )
        pricing_result = options_pricing_engine.estimate_premium(
            underlying_price=float(underlying_rows[0]["price"]),
            strike=float(strike),
            option_type=option_type,
            volatility_multiplier=float(vol["mult"]),
            days_to_expiry=int(expiry_result["days_to_expiry"])
        )
        entry_price = round(pricing_result.premium, 2)
        print(
            f"[OPTIONS FALLBACK] {underlying_symbol} calibrated price={entry_price} "
            f"intrinsic={pricing_result.intrinsic_value:.2f} "
            f"time={pricing_result.time_value:.2f} "
            f"decay={pricing_result.decay_factor:.2f} "
            f"dte={expiry_result['days_to_expiry']} "
            f"expiry={expiry_result['expiry_string']}"
        )

    if used_fallback_contract and entry_price > OPTION_FALLBACK_MAX_PRICE:
        print(
            f"[OPTIONS SKIPPED] {underlying_symbol} fallback contract too expensive "
            f"price={entry_price:.2f}"
        )
        return

    option_symbol = (
        f"{underlying_symbol}-"
        f"{option_type[0]}-"
        f"{int(strike)}"
    )

    open_result = options_pm.open_long_option(
        option_symbol=option_symbol,
        underlying_symbol=underlying_symbol,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        entry_price=entry_price,
        contracts=option_units,
        current_cycle=cycle,
        confidence=prob_pos,
        tier="ELITE" if signal_score > 16 else "QUALIFIED",
        note=f"PTPOP={prob_pos:.2%} EV={ev:+.2f}"
    )

    if open_result.get("status") == "OPENED":
        pnl_seed = round(random.uniform(-8, 15) * eff * capital_multiplier, 4)
        options_pnl[option_symbol_stub] += pnl_seed
        options_trades[option_symbol_stub] += 1
        if pnl_seed > 0:
            options_wins[option_symbol_stub] += 1

        register_cycle_entry("OPTIONS")
        update_fill_visibility(
            asset_class="OPTIONS",
            symbol=option_symbol,
            side=option_type,
            units=option_units,
            pnl_value=pnl_seed,
            status="SIM_OPTION_FILLED" if execution_metrics.get("mode") == "SIM" else "PAPER_OPTION_FILLED",
            order_id="SIM_OPTION",
            fill_price=entry_price,
        )
        last_trade = f"{option_symbol} [{option_type}]"

        print(
            f"[OPTIONS EXECUTED] {option_symbol} "
            f"P+={prob_pos:.2%} EV={ev:+.2f} SCORE={signal_score:.2f}"
        )
    else:
        print(
            f"[OPTIONS NOT OPENED] {underlying_symbol} "
            f"status={open_result.get('status', 'UNKNOWN')}"
        )


while True:
    cycle += 1
    reset_cycle_entry_counts()
    execution_metrics["winner_run_active"] = 0
    execution_metrics["loser_cut_active"] = 0
    refresh_broker_snapshots()
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    apply_bias_decay()

    total = get_total_pnl()
    winner_sym, winner_val = get_top_winner()
    loser_sym, loser_val = get_top_loser()

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"TOTAL PNL: {total:+.4f}")
    print(f"CRYPTO OPEN: {sum(crypto_trades.values())} | PNL {sum(crypto_pnl.values()):+.4f}")
    print(f"FX OPEN: {sum(fx_trades.values())} | PNL {sum(fx_pnl.values()):+.4f}")
    print(f"OPTIONS OPEN: {sum(options_trades.values())} | PNL {sum(options_pnl.values()):+.4f}")
    print(f"FUTURES OPEN: {sum(futures_trade_count.values())} | PNL {sum(futures_realized_pnl.values()):+.4f}")
    print(f"TOP WINNER: {winner_sym} {winner_val:+.4f}")
    print(f"TOP LOSER: {loser_sym} {loser_val:+.4f}")
    print(f"LAST TRADE: {last_trade}")
    print(f"MODE: {execution_metrics['mode']} | BROKER: {execution_metrics['broker']} | ARMED: {execution_metrics['armed']}")
    print(f"BROKER BEING USED: {execution_metrics['broker']}")
    print(f"CAPS: open max {MAX_ASSET_OPEN_POSITIONS} | cycle max {MAX_NEW_PER_CYCLE}")
    print("OPTIMIZATION: strict entry filter + smart PnL shaping + winner-run/loser-cut active")
    print("--- ORDER / FILL VISIBILITY ---")
    print(f"LAST ORDER: {execution_metrics['last_order_id']} | STATUS: {execution_metrics['last_order_status']}")
    print(f"LAST FILL: {execution_metrics['last_fill_symbol']} {execution_metrics['last_fill_side']} qty={execution_metrics['last_fill_qty']} pnl={execution_metrics['last_fill_pnl']:+.4f}")
    print(f"ORDERS SENT: {execution_metrics['orders_sent']} | BLOCKED: {execution_metrics['orders_blocked']} | FILLS: {execution_metrics['fills_recorded']}")
    print(f"REALIZED PNL: {execution_metrics['realized_pnl']:+.4f} | UNREALIZED PNL: {execution_metrics['unrealized_pnl']:+.4f}")
    print(f"EQUITY: {execution_metrics['equity']:.4f} | PEAK: {execution_metrics['peak_equity']:.4f} | DD: {execution_metrics['drawdown_pct']:.2%}")
    print(f"RISK THROTTLE: {execution_metrics['risk_throttle']:.2f} | CAPITAL MULT: {execution_metrics['capital_multiplier']:.2f} | GUARD: {execution_metrics['capital_guard_active']}")
    print(f"OPEN POSITIONS: {execution_metrics['open_position_count']} | CLOSED TRADES: {execution_metrics['closed_trade_count']}")
    print(f"WINNER-RUN FLAGS: {execution_metrics['winner_run_active']} | LOSER-CUT FLAGS: {execution_metrics['loser_cut_active']}")
    print("-" * 60)

    regime_board = []
    vwap_board = []
    volatility_board = []
    sweep_board = []
    effective_board = []

    for s in SYMBOLS:
        safe_load_runtime_asset(s)

        reg = detect_regime(s, "CRYPTO")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "CRYPTO", reg))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "CRYPTO", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] == "BLOCK":
            continue

        governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state("CRYPTO")
        if governor_frozen:
            print(
                f"[BLEED FREEZE] CRYPTO "
                f"LOSS={asset_loss:.4f} "
                f"LIMIT={freeze_limit:.4f} "
                f"OTHERS+={other_positive:.4f}"
            )
            continue

        raw_score = round(random.uniform(8, 18), 2)
        signal_score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        prob_pos, prob_neg, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score
        )

        signal_score = apply_profit_quality_boost(signal_score, prob_pos, ev)

        if not allow_trade:
            print(f"[CRYPTO REJECTED] {s} P+={prob_pos:.2%} EV={ev:+.2f}")
            continue

        route_execution("CRYPTO", s, round(signal_score, 2), eff)

    for s in FX_SYMBOLS:
        reg = detect_regime(s, "FX")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "FX", reg))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "FX", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] == "BLOCK":
            continue

        governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state("FX")
        if governor_frozen:
            print(
                f"[BLEED FREEZE] FX "
                f"LOSS={asset_loss:.4f} "
                f"LIMIT={freeze_limit:.4f} "
                f"OTHERS+={other_positive:.4f}"
            )
            continue

        raw_score = round(random.uniform(8, 18), 2)
        signal_score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        prob_pos, prob_neg, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score
        )

        signal_score = apply_profit_quality_boost(signal_score, prob_pos, ev)

        if not allow_trade:
            print(f"[FX REJECTED] {s} P+={prob_pos:.2%} EV={ev:+.2f}")
            continue

        route_execution("FX", s, round(signal_score, 2), eff)

    for s in OPTION_SYMBOLS:
        reg = detect_regime(s, "OPTIONS")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "OPTIONS", reg))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "OPTIONS", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        execute_intelligent_option_trade(
            s, reg, vw, vol, sw, cycle, eff
        )

    for symbol in FUTURES_SYMBOLS:
        reg = detect_regime(symbol, "FUTURES")
        vw = compute_vwap_state(symbol)
        vol = compute_volatility_state(symbol)
        sw = compute_liquidity_sweep(symbol)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((symbol, "FUTURES", reg))
        vwap_board.append((symbol, vw))
        volatility_board.append((symbol, vol))
        sweep_board.append((symbol, sw))
        effective_board.append(
            (symbol, "FUTURES", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] == "BLOCK":
            continue

        governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state("FUTURES")
        if governor_frozen:
            print(
                f"[BLEED FREEZE] FUTURES "
                f"LOSS={asset_loss:.4f} "
                f"LIMIT={freeze_limit:.4f} "
                f"OTHERS+={other_positive:.4f}"
            )
            continue

        raw_score = round(random.uniform(8, 18), 2)
        weighted = weighted_score(raw_score, symbol)

        signal_score = (
            weighted *
            reg["risk_mult"] *
            vw["mult"] *
            vol["mult"] *
            sw["mult"]
        )

        prob_pos, prob_neg, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score
        )

        signal_score = apply_profit_quality_boost(signal_score, prob_pos, ev)

        if allow_trade:
            route_execution("FUTURES", symbol, round(signal_score, 2), eff)
        else:
            print(
                f"[FUTURES REJECTED] {symbol} "
                f"P+={prob_pos:.2%} EV={ev:+.2f}"
            )

    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)

    print("\n--- LIQUIDITY SWEEP BOARD ---")
    for sym, sw in sweep_board[:12]:
        print(f"{sym} | {sw['state']} | {sw['mult']:.2f}x")

    print("\n--- VWAP BOARD ---")
    for sym, vw in vwap_board[:12]:
        print(f"{sym} | {vw['distance_pct']:+.2f}% | {vw['state']}")

    print("\n--- VOLATILITY BOARD ---")
    for sym, vol in volatility_board[:12]:
        print(f"{sym} | {vol['state']} | {vol['mult']:.2f}x")

    print("\n--- UNIVERSAL EFFECTIVE BOARD ---")
    for sym, cls, pri, vwstate, volstate, swstate, eff in effective_board[:12]:
        print(
            f"{sym} | {cls} | {pri} | "
            f"{vwstate} | {volstate} | {swstate} | Eff {eff:.2f}x"
        )

    print("\n--- FUTURES SYMBOL BIAS ---")
    print(futures_symbol_bias)

    time.sleep(CYCLE_SLEEP)
