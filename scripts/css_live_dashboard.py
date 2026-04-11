from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================
# CORE IMPORTS
# =========================
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager

from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager

from backend.scanner.options_chain_adapter import OptionsChainAdapter
from backend.options.options_position_manager import OptionsPositionManager
from backend.options.options_intelligence_engine import OptionsIntelligenceEngine

# =========================================================
# ENGINE MODES
# =========================================================
ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

ENGINE_PROFILES = {
    "SAFE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1, "MAX_FX": 1},
    "CONSERVATIVE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1, "MAX_FX": 2},
    "BALANCED": {"MAX_CRYPTO": 3, "MAX_OPTIONS": 2, "MAX_FX": 3},
    "AGGRESSIVE": {"MAX_CRYPTO": 4, "MAX_OPTIONS": 3, "MAX_FX": 4},
    "EXPANSION": {"MAX_CRYPTO": 5, "MAX_OPTIONS": 4, "MAX_FX": 5},
}


def select_engine_mode():
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice, "BALANCED")


ENGINE_MODE = select_engine_mode()
PROFILE = ENGINE_PROFILES[ENGINE_MODE]

MAX_CRYPTO = PROFILE["MAX_CRYPTO"]
MAX_OPTIONS = PROFILE["MAX_OPTIONS"]
MAX_FX = PROFILE["MAX_FX"]

CYCLE_SLEEP = 3

# =========================================================
# PARAMETERS
# =========================================================
TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD = 3

FX_TP_PCT = 0.004
FX_SL_PCT = 0.003
FX_MAX_HOLD = 3
FX_ACCOUNT_EQUITY = 10000.0

OPTION_MIN_PREMIUM = 0.001
OPTION_MAX_PREMIUM = 50.0
OPTION_PREMIUM_TO_UNDERLYING_MAX = 0.40

OPTION_TP_PCT = 0.18
OPTION_SL_PCT = 0.12
OPTION_TRAIL_ARM_PCT = 0.10
OPTION_TRAIL_GIVEBACK_PCT = 0.06
OPTION_MAX_HOLD = 3

# =========================================================
# SYMBOL UNIVERSES
# =========================================================
SYMBOLS = [
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
]

FX_SYMBOLS = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "NZD_USD",
]

FX_BASE_PRICES = {
    "EUR_USD": 1.0850,
    "GBP_USD": 1.2720,
    "USD_JPY": 151.20,
    "AUD_USD": 0.6570,
    "USD_CAD": 1.3520,
    "USD_CHF": 0.9010,
    "NZD_USD": 0.6120,
}

# =========================================================
# ENGINES
# =========================================================
pm = PositionManager()

futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()

# =========================================================
# STATE
# =========================================================
prev_prices: Dict[str, float] = {}

pos_cycles: Dict[str, int] = {}
fx_cycles: Dict[str, int] = {}

option_open_cycles: Dict[str, int] = {}
option_peak_pnl: Dict[str, float] = {}
option_entry_underlying: Dict[str, float] = {}
option_entry_tier: Dict[str, str] = {}

# realized pnl ledgers
crypto_realized_pnl: Dict[str, float] = {}
fx_realized_pnl: Dict[str, float] = {}
options_realized_pnl: Dict[str, float] = {}

# =========================================================
# HELPERS
# =========================================================
def safe(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def safe_str(v, d=""):
    try:
        s = str(v).strip()
        return s if s else d
    except Exception:
        return d


def add_realized_pnl(ledger: Dict[str, float], symbol: str, pnl: float):
    symbol = safe_str(symbol, "UNKNOWN")
    ledger[symbol] = round(ledger.get(symbol, 0.0) + safe(pnl, 0.0), 4)


def total_realized_pnl() -> float:
    return round(
        sum(crypto_realized_pnl.values())
        + sum(fx_realized_pnl.values())
        + sum(options_realized_pnl.values()),
        4,
    )


def print_realized_section(title: str, ledger: Dict[str, float]):
    non_zero = {k: v for k, v in ledger.items() if abs(v) > 1e-12}
    print(title)
    if not non_zero:
        print("  none")
        return

    for sym, pnl in sorted(non_zero.items(), key=lambda x: x[0]):
        print(f"  {sym}: {pnl:.4f}")


def classify_signal(score):
    if score >= 10:
        return "ELITE"
    if score >= 4.5:
        return "QUALIFIED"
    return "WATCH"


def size_for(tier):
    if tier == "ELITE":
        return 1.0
    if tier == "QUALIFIED":
        return 0.5
    return 0.0


def score(symbol, price, prev):
    if prev <= 0:
        return 0.0
    return abs((price - prev) / prev) * 10000


def option_symbol(underlying, best):
    strike = safe(best.get("strike"))
    expiry = str(best.get("expiry") or "NA")
    return f"{underlying}_CALL_{strike:.2f}_{expiry}"


def get_fx_price(symbol: str) -> float:
    prev = safe(prev_prices.get(symbol), 0.0)
    base = safe(FX_BASE_PRICES.get(symbol), 1.0)

    if prev <= 0:
        return base

    t = int(time.time()) % 6

    if t == 0:
        drift = 1.0025
    elif t == 1:
        drift = 0.9980
    elif t == 2:
        drift = 1.0032
    elif t == 3:
        drift = 0.9975
    elif t == 4:
        drift = 1.0018
    else:
        drift = 0.9988

    return round(prev * drift, 6)

# =========================================================
# OPTIONS EDGE FILTER
# =========================================================
def option_has_reasonable_premium(premium, underlying_price):
    if premium < OPTION_MIN_PREMIUM:
        return False, "premium too low"
    if premium > OPTION_MAX_PREMIUM:
        return False, "premium too high"
    if underlying_price <= 0:
        return False, "bad underlying"
    if premium / underlying_price > OPTION_PREMIUM_TO_UNDERLYING_MAX:
        return False, "premium ratio too high"
    return True, "pass"


def option_has_sufficient_edge(score_value, premium, underlying_price, tier):
    if underlying_price <= 0:
        return False, "bad underlying"

    expected_move = (score_value / 10000.0) * 1.8
    premium_cost = premium / underlying_price

    if tier == "ELITE":
        factor = 0.35
    elif tier == "QUALIFIED":
        factor = 0.45
    else:
        return False, "watch tier"

    hurdle = premium_cost * factor

    print(
        f"[OPTION DIAG] score={score_value:.2f} "
        f"exp_move={expected_move:.6f} "
        f"premium={premium:.6f} "
        f"ratio={premium_cost:.6f} "
        f"hurdle={hurdle:.6f} tier={tier}"
    )

    if expected_move < hurdle:
        return False, "weak edge"

    return True, "pass"

# =========================================================
# OPTION REPRICING ENGINE
# =========================================================
def estimate_option_reprice(option_sym, pos, current_underlying_price):
    entry_premium = safe(pos.get("entry_price"), 0.0)
    entry_underlying = option_entry_underlying.get(option_sym, current_underlying_price)
    tier = option_entry_tier.get(option_sym, "QUALIFIED")

    if entry_premium <= 0:
        return 0.0

    move_pct = 0.0
    if entry_underlying > 0:
        move_pct = (current_underlying_price - entry_underlying) / entry_underlying

    if tier == "ELITE":
        delta = 0.65
    elif tier == "QUALIFIED":
        delta = 0.55
    else:
        delta = 0.45

    repriced = entry_premium * (1 + move_pct * delta * 6.0)
    repriced *= 0.995
    repriced = max(repriced, entry_premium * 0.35)

    return round(repriced, 6)


def get_open_option_positions():
    try:
        open_positions = options_pm.get_open_positions()
    except Exception:
        return []

    normalized = []
    for idx, pos in enumerate(open_positions):
        sym = safe_str(pos.get("option_symbol") or pos.get("symbol"), f"OPT_{idx}")
        normalized.append((sym, pos))
    return normalized


def try_close_option_position(option_sym, current_price, reason, cycle):
    try:
        result = options_pm.close_position(
            option_symbol=option_sym,
            exit_price=current_price,
            reason=reason,
            closed_cycle=cycle,
        )
        print(f"[OPTIONS CLOSE SIGNAL] {option_sym} reason={reason} exit={current_price:.4f}")

        if result.get("status") == "CLOSED":
            add_realized_pnl(
                options_realized_pnl,
                safe_str(result.get("option_symbol"), option_sym),
                safe(result.get("pnl"), 0.0),
            )
            return True

        return False
    except Exception as e:
        print(f"[OPTIONS CLOSE ERROR] {option_sym}: {e}")
        return False


def evaluate_option_profit_capture(option_price_map, price_map, cycle):
    for option_sym, pos in get_open_option_positions():
        entry = safe(pos.get("entry_price"), 0.0)
        underlying_symbol = safe_str(pos.get("underlying_symbol"))
        current_underlying = safe(price_map.get(underlying_symbol), 0.0)

        repriced_value = estimate_option_reprice(option_sym, pos, current_underlying)
        chain_value = safe(option_price_map.get(option_sym), 0.0)
        current = max(chain_value, repriced_value) if chain_value > 0 else repriced_value

        if entry <= 0 or current <= 0:
            continue

        pnl = (current - entry) / entry
        peak = option_peak_pnl.get(option_sym, pnl)
        if pnl > peak:
            peak = pnl
        option_peak_pnl[option_sym] = peak

        opened_cycle = option_open_cycles.get(option_sym, cycle)
        hold_cycles = max(0, cycle - opened_cycle)

        print(
            f"[OPTION PNL] {option_sym} "
            f"entry={entry:.4f} current={current:.4f} "
            f"repriced={repriced_value:.4f} "
            f"pnl={pnl:.2%} peak={peak:.2%} hold={hold_cycles}"
        )

        reason = None
        if pnl >= OPTION_TP_PCT:
            reason = "TP"
        elif pnl <= -OPTION_SL_PCT:
            reason = "SL"
        elif peak >= OPTION_TRAIL_ARM_PCT and pnl <= (peak - OPTION_TRAIL_GIVEBACK_PCT):
            reason = "TRAIL"
        elif hold_cycles >= OPTION_MAX_HOLD:
            reason = "TIME"

        if reason:
            closed = try_close_option_position(option_sym, current, reason, cycle)
            if closed:
                option_open_cycles.pop(option_sym, None)
                option_peak_pnl.pop(option_sym, None)
                option_entry_underlying.pop(option_sym, None)
                option_entry_tier.pop(option_sym, None)

# =========================================================
# FX HELPERS
# =========================================================
def get_open_fx_positions():
    try:
        return futures_pm.get_open_positions()
    except Exception:
        return []


def get_fx_positions_by_symbol():
    out = {}
    for pos in get_open_fx_positions():
        sym = safe_str(pos.get("symbol"))
        if sym:
            out[sym] = pos
    return out


def get_fx_position_id_by_symbol(symbol: str):
    for pos in get_open_fx_positions():
        if safe_str(pos.get("symbol")) == symbol:
            return safe_str(pos.get("position_id"))
    return ""

# =========================================================
# MAIN LOOP
# =========================================================
cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    rows = []
    price_map = {}
    fx_rows = []
    fx_price_map = {}

    # CRYPTO FETCH
    for s in SYMBOLS:
        raw = load_runtime_asset(s)
        price = safe(raw.get("price") or raw.get("close"))
        sc = score(s, price, prev_prices.get(s, 0))
        rows.append({"symbol": s, "price": price, "score": sc})
        price_map[s] = price

    rows.sort(key=lambda x: -x["score"])

    # FX FETCH
    for fx in FX_SYMBOLS:
        try:
            fx_price = get_fx_price(fx)
            fx_score = score(fx, fx_price, prev_prices.get(fx, 0))
            fx_rows.append({"symbol": fx, "price": fx_price, "score": fx_score})
            fx_price_map[fx] = fx_price
        except Exception as e:
            print(f"[FX FETCH ERROR] {fx}: {e}")

    fx_rows.sort(key=lambda x: -x["score"])

    # DISPLAY
    print("\n--- CRYPTO ---")
    for r in rows[:5]:
        print(f"{r['symbol']} | score={r['score']:.2f} | tier={classify_signal(r['score'])}")

    print("\n--- FX ---")
    for r in fx_rows[:5]:
        print(f"{r['symbol']} | score={r['score']:.2f} | tier={classify_signal(r['score'])}")

    # CRYPTO UPDATE
    try:
        pm.update_positions(price_map)
        for sym, pos in list(pm.positions.items()):
            entry = safe(pos.get("entry_price"))
            cur = safe(price_map.get(sym))
            size = safe(pos.get("size"), 1.0)
            pnl = (cur - entry) / entry if entry > 0 else 0
            pos_cycles[sym] = pos_cycles.get(sym, 0) + 1

            print(f"{sym} | size={pos.get('size')} | pnl={pnl:.4%}")

            if pnl >= TP_PCT or pnl <= -SL_PCT or pos_cycles[sym] >= MAX_HOLD:
                realized = (cur - entry) * size
                add_realized_pnl(crypto_realized_pnl, sym, realized)
                pm.close_position(sym, cur, "TIME")
                pos_cycles.pop(sym, None)
    except Exception as e:
        print(f"[CRYPTO UPDATE ERROR] {e}")

    # FX UPDATE
    try:
        fx_by_symbol = get_fx_positions_by_symbol()
        for sym, pos in list(fx_by_symbol.items()):
            cur = safe(fx_price_map.get(sym))
            entry = safe(pos.get("entry_price"))
            pnl = (cur - entry) / entry if entry > 0 else 0
            fx_cycles[sym] = fx_cycles.get(sym, 0) + 1

            print(f"{sym} | FX pnl={pnl:.4%}")

            position_id = get_fx_position_id_by_symbol(sym)
            if not position_id:
                continue

            if pnl >= FX_TP_PCT or pnl <= -FX_SL_PCT or fx_cycles[sym] >= FX_MAX_HOLD:
                result = futures_pm.close_position(position_id, cur)
                if result.get("status") == "CLOSED":
                    pos_data = result.get("position", {})
                    add_realized_pnl(
                        fx_realized_pnl,
                        safe_str(pos_data.get("symbol"), sym),
                        safe(pos_data.get("pnl"), 0.0),
                    )
                fx_cycles.pop(sym, None)
    except Exception as e:
        print(f"[FX UPDATE ERROR] {e}")

    # CRYPTO OPEN
    open_crypto = len(getattr(pm, "positions", {}))
    for r in rows:
        if open_crypto >= MAX_CRYPTO:
            break
        if r["symbol"] in getattr(pm, "positions", {}):
            continue

        tier = classify_signal(r["score"])
        if tier == "WATCH":
            continue

        size = size_for(tier)
        if size <= 0:
            continue

        try:
            pm.open_position(
                symbol=r["symbol"],
                entry_price=r["price"],
                size=size,
                take_profit=r["price"] * (1 + TP_PCT),
                stop_loss=r["price"] * (1 - SL_PCT),
                side="LONG",
            )
            print(f"[CRYPTO OPEN] {r['symbol']} ({tier}) size={size}")
            open_crypto += 1
        except Exception as e:
            print(f"[CRYPTO OPEN ERROR] {r['symbol']}: {e}")

    # FX OPEN
    open_fx = len(get_open_fx_positions())
    existing_fx_symbols = set(get_fx_positions_by_symbol().keys())

    for r in fx_rows:
        if open_fx >= MAX_FX:
            break
        if r["symbol"] in existing_fx_symbols:
            continue

        tier = classify_signal(r["score"])
        if tier == "WATCH":
            continue

        try:
            stop_price = r["price"] * (1 - FX_SL_PCT)
            contracts = 1 if tier in ("ELITE", "QUALIFIED") else 0

            if contracts <= 0:
                continue

            res = futures_pm.open_position(
                symbol=r["symbol"],
                entry_price=r["price"],
                stop_price=stop_price,
                contracts=contracts,
                current_equity=FX_ACCOUNT_EQUITY,
                state={"engine_mode": ENGINE_MODE, "cycle": cycle},
            )

            if res.get("status") == "OPENED":
                print(f"[FX OPEN] {r['symbol']} ({tier}) contracts={contracts}")
                open_fx += 1
                existing_fx_symbols.add(r["symbol"])
            else:
                print(f"[FX REJECTED] {r['symbol']} {res.get('reason')}")
        except Exception as e:
            print(f"[FX OPEN ERROR] {r['symbol']}: {e}")

    # OPTIONS ENGINE
    executed_options = 0
    try:
        opts = options_adapter.fetch_option_rows(
            [{"symbol": r["symbol"], "price": r["price"]} for r in rows[:3]]
        )

        print(f"\nOptions Visible: {len(opts)}")
        open_options = len(get_open_option_positions())

        for r in rows[:3]:
            if open_options >= MAX_OPTIONS:
                break

            underlying = r["symbol"]
            tier = classify_signal(r["score"])
            if tier == "WATCH":
                continue

            best = options_intel.select_best_option(
                options=[o for o in opts if o.get("symbol") == underlying],
                underlying_price=r["price"],
                score=r["score"],
                tier=tier,
            )

            if not best:
                continue

            premium = safe(best.get("price"), 0.0)

            ok_premium, reason = option_has_reasonable_premium(premium, r["price"])
            if not ok_premium:
                print(f"[OPTIONS FILTERED] {underlying} {reason}")
                continue

            ok_edge, edge_reason = option_has_sufficient_edge(
                r["score"], premium, r["price"], tier
            )
            if not ok_edge:
                print(f"[OPTIONS FILTERED] {underlying} {edge_reason}")
                continue

            sym = option_symbol(underlying, best)
            existing = {s for s, _ in get_open_option_positions()}
            if sym in existing:
                continue

            res = options_pm.open_long_option(
                option_symbol=sym,
                underlying_symbol=underlying,
                option_type="CALL",
                strike=safe(best.get("strike")),
                expiry=str(best.get("expiry")),
                entry_price=premium,
                contracts=1,
                current_cycle=cycle,
                confidence=r["score"],
                tier=tier,
            )

            if res.get("status") == "OPENED":
                print(f"[OPTIONS OPEN] {sym} ({tier}) premium={premium:.4f}")
                executed_options += 1
                open_options += 1
                option_open_cycles[sym] = cycle
                option_peak_pnl[sym] = 0.0
                option_entry_underlying[sym] = r["price"]
                option_entry_tier[sym] = tier

        option_price_map = {
            option_symbol(o.get("symbol"), o): safe(o.get("price"), 0.0)
            for o in opts
        }

        evaluate_option_profit_capture(option_price_map, price_map, cycle)

    except Exception as e:
        print(f"[OPTIONS ERROR] {e}")

    # SUMMARY
    print("\n--- PROFIT DASHBOARD ---")
    print(f"Engine Mode: {ENGINE_MODE}")
    print(f"Crypto Open: {len(getattr(pm, 'positions', {}))}")
    print(f"FX Open: {len(get_open_fx_positions())}")
    print(f"Options Open: {len(get_open_option_positions())}")
    print(f"Executed Options This Cycle: {executed_options}")

    print("\n--- REALIZED PNL ---")
    print_realized_section("Crypto Realized:", crypto_realized_pnl)
    print_realized_section("FX Realized:", fx_realized_pnl)
    print_realized_section("Options Realized:", options_realized_pnl)
    print(f"Total Realized PnL: {total_realized_pnl():.4f}")

    prev_prices.update(price_map)
    prev_prices.update(fx_price_map)

    time.sleep(CYCLE_SLEEP)