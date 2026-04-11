from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager
from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager
from backend.scanner.options_chain_adapter import OptionsChainAdapter
from backend.options.options_position_manager import OptionsPositionManager
from backend.options.options_intelligence_engine import OptionsIntelligenceEngine

# ========================
# ENGINE MODES
# ========================
ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

ENGINE_PROFILES = {
    "SAFE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1},
    "CONSERVATIVE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1},
    "BALANCED": {"MAX_CRYPTO": 3, "MAX_OPTIONS": 2},
    "AGGRESSIVE": {"MAX_CRYPTO": 4, "MAX_OPTIONS": 3},
    "EXPANSION": {"MAX_CRYPTO": 5, "MAX_OPTIONS": 4},
}


def select_engine_mode():
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice, "BALANCED")


ENGINE_MODE = select_engine_mode()
PROFILE = ENGINE_PROFILES[ENGINE_MODE]

# ========================
# CONFIG
# ========================
CYCLE_SLEEP = 3
MAX_CRYPTO = PROFILE["MAX_CRYPTO"]
MAX_OPTIONS = PROFILE["MAX_OPTIONS"]

MIN_SCORE = 0.08
TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD = 3

OPTION_MIN_PREMIUM = 0.001
OPTION_MAX_PREMIUM = 50.0
OPTION_PREMIUM_TO_UNDERLYING_MAX = 0.40

# OPTIONS PROFIT CAPTURE
OPTION_TP_PCT = 0.18
OPTION_SL_PCT = 0.12
OPTION_TRAIL_ARM_PCT = 0.10
OPTION_TRAIL_GIVEBACK_PCT = 0.06
OPTION_MAX_HOLD = 3

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD",
    "LTC-USD", "BCH-USD"
]

# ========================
# INIT
# ========================
pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()

prev_prices: Dict[str, float] = {}
pos_cycles: Dict[str, int] = {}

# option trackers
option_open_cycles: Dict[str, int] = {}
option_peak_pnl: Dict[str, float] = {}

# ========================
# HELPERS
# ========================
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


def classify_signal(score):
    if score >= 10:
        return "ELITE"
    if score >= 4.5:
        return "QUALIFIED"
    return "WATCH"


def size_for(tier):
    return 1.0 if tier == "ELITE" else 0.5 if tier == "QUALIFIED" else 0.0


def score(symbol, price, prev):
    if prev <= 0:
        return 0.0
    return abs((price - prev) / prev) * 10000


def option_symbol(underlying, best):
    strike = safe(best.get("strike"))
    expiry = str(best.get("expiry") or "NA")
    return f"{underlying}_CALL_{strike:.2f}_{expiry}"


# =========================================================
# CALIBRATED EDGE MODEL
# =========================================================
def option_has_sufficient_edge(score_value, premium, underlying_price, tier):
    if underlying_price <= 0:
        return False, "bad underlying"

    expected_move = (score_value / 10000.0) * 1.8
    premium_cost = premium / underlying_price

    if premium_cost <= 0:
        return False, "bad premium cost"

    if tier == "ELITE":
        factor = 0.35
    elif tier == "QUALIFIED":
        factor = 0.45
    else:
        return False, "watch tier"

    hurdle = premium_cost * factor
    passed = expected_move >= hurdle

    print(
        f"[OPTION DIAG] "
        f"score={score_value:.2f} "
        f"exp_move={expected_move:.6f} "
        f"premium={premium:.6f} "
        f"ratio={premium_cost:.6f} "
        f"hurdle={hurdle:.6f} "
        f"tier={tier}"
    )

    if not passed:
        return False, "weak edge"

    return True, "pass"


def option_has_reasonable_premium(premium, underlying_price):
    if premium < OPTION_MIN_PREMIUM:
        return False, "premium too low"
    if premium > OPTION_MAX_PREMIUM:
        return False, "premium too high"
    if underlying_price <= 0:
        return False, "bad underlying"
    if (premium / underlying_price) > OPTION_PREMIUM_TO_UNDERLYING_MAX:
        return False, "premium ratio too high"
    return True, "pass"


# =========================================================
# OPTIONS PROFIT CAPTURE HELPERS
# =========================================================
def get_open_option_positions() -> List[Tuple[str, Dict[str, Any]]]:
    try:
        open_positions = options_pm.get_open_positions()
    except Exception:
        return []

    if isinstance(open_positions, dict):
        return list(open_positions.items())

    if isinstance(open_positions, list):
        normalized = []
        for idx, pos in enumerate(open_positions):
            if isinstance(pos, dict):
                sym = safe_str(
                    pos.get("option_symbol")
                    or pos.get("symbol")
                    or pos.get("position_id"),
                    f"OPT_{idx}"
                )
                normalized.append((sym, pos))
        return normalized

    return []


def try_close_option_position(option_sym: str, current_price: float, reason: str, cycle: int) -> bool:
    close_methods = [
        "close_option_position",
        "close_position",
        "close_long_option",
        "close_option",
    ]

    for method_name in close_methods:
        method = getattr(options_pm, method_name, None)
        if not callable(method):
            continue

        try:
            result = method(
                option_symbol=option_sym,
                exit_price=current_price,
                reason=reason,
                current_cycle=cycle,
            )
            print(f"[OPTIONS CLOSE SIGNAL] {option_sym} reason={reason} exit={current_price:.4f}")
            return True
        except TypeError:
            try:
                result = method(option_sym, current_price, reason, cycle)
                print(f"[OPTIONS CLOSE SIGNAL] {option_sym} reason={reason} exit={current_price:.4f}")
                return True
            except Exception:
                pass
        except Exception:
            pass

        try:
            result = method(option_sym, current_price)
            print(f"[OPTIONS CLOSE SIGNAL] {option_sym} reason={reason} exit={current_price:.4f}")
            return True
        except Exception:
            pass

    print(f"[OPTIONS HOLD] {option_sym} close-method unavailable for reason={reason}")
    return False


def evaluate_option_profit_capture(option_price_map: Dict[str, float], cycle: int):
    for option_sym, pos in get_open_option_positions():
        entry = safe(
            pos.get("entry_price")
            or pos.get("avg_price")
            or pos.get("price"),
            0.0,
        )
        current = safe(option_price_map.get(option_sym), 0.0)

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


# ========================
# LOOP
# ========================
cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    rows = []
    price_map = {}

    for s in SYMBOLS:
        try:
            raw = load_runtime_asset(s)
            price = safe(raw.get("price") or raw.get("close"))
            sc = score(s, price, prev_prices.get(s, 0))
            rows.append({"symbol": s, "price": price, "score": sc})
            price_map[s] = price
        except Exception as e:
            print(f"[DATA ERROR] {s}: {e}")

    rows.sort(key=lambda x: -x["score"])

    print("\n--- CRYPTO ---")
    for r in rows[:5]:
        tier = classify_signal(r["score"])
        print(f"{r['symbol']} | score={r['score']:.2f} | tier={tier}")

    pm.update_positions(price_map)

    for sym, pos in list(pm.positions.items()):
        entry = safe(pos.get("entry_price"))
        cur = safe(price_map.get(sym))
        pnl = (cur - entry) / entry if entry > 0 else 0
        pos_cycles[sym] = pos_cycles.get(sym, 0) + 1

        print(f"{sym} | size={pos.get('size')} | pnl={pnl:.4%}")

        if pnl >= TP_PCT or pnl <= -SL_PCT or pos_cycles[sym] >= MAX_HOLD:
            pm.close_position(sym, cur, "TIME")
            pos_cycles.pop(sym, None)

    # ===== CRYPTO ENTRY =====
    open_crypto = len(pm.positions)

    for r in rows:
        if open_crypto >= MAX_CRYPTO:
            break
        if r["symbol"] in pm.positions:
            continue

        tier = classify_signal(r["score"])
        if tier == "WATCH":
            continue

        size = size_for(tier)
        if size <= 0:
            continue

        pm.open_position(
            symbol=r["symbol"],
            entry_price=r["price"],
            size=size,
            take_profit=r["price"] * (1 + TP_PCT),
            stop_loss=r["price"] * (1 - SL_PCT),
            side="LONG"
        )

        print(f"[CRYPTO OPEN] {r['symbol']} ({tier}) size={size}")
        open_crypto += 1

    # ===== OPTIONS ENTRY =====
    option_rows = []
    executed_options = 0

    try:
        opts = options_adapter.fetch_option_rows(
            [{"symbol": r["symbol"], "price": r["price"]} for r in rows[:3]]
        )

        option_rows = opts
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
                tier=tier
            )

            if not best:
                print(f"[OPTIONS FILTERED] {underlying} no contract")
                continue

            premium = safe(best.get("price"), 0.0)

            ok_premium, reason = option_has_reasonable_premium(
                premium, r["price"]
            )
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

            existing_symbols = {s for s, _ in get_open_option_positions()}
            if sym in existing_symbols:
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
                tier=tier
            )

            if res.get("status") == "OPENED":
                print(f"[OPTIONS OPEN] {sym} ({tier}) premium={premium:.4f}")
                executed_options += 1
                open_options += 1
                option_open_cycles[sym] = cycle
                option_peak_pnl[sym] = 0.0

    except Exception as e:
        print(f"[OPTIONS ERROR] {e}")

    # ===== OPTIONS UPDATE / PROFIT CAPTURE =====
    option_price_map = {
        option_symbol(o.get("symbol"), o): safe(o.get("price"), 0.0)
        for o in option_rows
    }

    evaluate_option_profit_capture(option_price_map, cycle)

    try:
        events = options_pm.update_positions(option_price_map, current_cycle=cycle)
    except Exception as e:
        events = []
        print(f"[OPTIONS UPDATE ERROR] {e}")

    for e in events:
        print(f"[OPTIONS CLOSED] {e.get('option_symbol')} pnl={e.get('pnl')}")
        closed_sym = safe_str(e.get("option_symbol"))
        if closed_sym:
            option_open_cycles.pop(closed_sym, None)
            option_peak_pnl.pop(closed_sym, None)

    # ===== DASHBOARD =====
    print("\n--- PROFIT DASHBOARD ---")
    print(f"Engine Mode: {ENGINE_MODE}")
    print(f"Crypto Open: {len(pm.positions)}")
    print(f"Options Open: {len(get_open_option_positions())}")
    print(f"Executed Options This Cycle: {executed_options}")

    prev_prices.update(price_map)
    time.sleep(CYCLE_SLEEP)