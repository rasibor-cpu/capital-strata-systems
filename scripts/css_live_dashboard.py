from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = PROJECT_ROOT / "audit_logs"
AUDIT_DIR.mkdir(exist_ok=True)
TRADE_LOG = AUDIT_DIR / "trades.jsonl"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_universe
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer


# ================= ACCOUNT =================
START_CAPITAL = 1000.0
equity = START_CAPITAL

stats = {
    "trades": 0,
    "wins": 0,
    "losses": 0,
    "pnl": 0.0,
}

cycle_count = 0


# ================= CONFIG =================
TOTAL_CAPITAL = 1000.0

CLASS_WEIGHTS = {
    "crypto": 0.40,
    "fx": 0.30,
    "futures": 0.30,
    "options": 0.00,
}

CLASS_LIMITS = {
    "crypto": 3,
    "fx": 3,
    "futures": 2,
    "options": 2,
}

MAX_OPEN_POSITIONS = 10
MAX_CYCLES = 10

BASE_FEE_BPS = {
    "crypto": 12.0,
    "fx": 4.0,
    "futures": 5.0,
    "options": 10.0,
}

DEFAULT_SPREAD_BPS = {
    "crypto": 8.0,
    "fx": 2.0,
    "futures": 3.0,
    "options": 8.0,
}

SAFETY_MARGIN_BPS = 2.0

PRODUCTS_BY_CLASS = {
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD"],
    "fx": ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD"],
    "futures": ["ES", "NQ", "CL", "GC", "ZN"],
    "options": [],
}

PRODUCTS_NO_CRYPTO = PRODUCTS_BY_CLASS["fx"] + PRODUCTS_BY_CLASS["futures"]

open_positions: Dict[str, Dict] = {}
last_prices: Dict[str, float] = {}


# ================= HELPERS =================
def safe_float(v, d: float = 0.0) -> float:
    try:
        if v is None:
            return d
        return float(v)
    except Exception:
        return d


def symbol_asset_class(symbol: str) -> str:
    for k, v in PRODUCTS_BY_CLASS.items():
        if symbol in v:
            return k
    return "unknown"


def count_open_positions_by_class() -> Dict[str, int]:
    counts = {k: 0 for k in CLASS_LIMITS}
    for s in open_positions:
        cls = symbol_asset_class(s)
        if cls in counts:
            counts[cls] += 1
    return counts


def log_trade(data: Dict) -> None:
    with open(TRADE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")


def print_performance() -> None:
    win_rate = (stats["wins"] / stats["trades"] * 100.0) if stats["trades"] else 0.0
    print("\n===== PERFORMANCE =====")
    print(f"Equity: ${equity:.2f}")
    print(f"PnL: {stats['pnl']:+.2f}")
    print(
        f"Trades: {stats['trades']} | Wins: {stats['wins']} | "
        f"Losses: {stats['losses']} | Win Rate: {win_rate:.1f}%"
    )
    print("======================\n")


def ensure_vwap_dev(r: Dict) -> Dict:
    price = safe_float(r.get("price"), 0.0)
    vwap = safe_float(r.get("vwap"), price)

    if price <= 0:
        r["vwap_dev"] = 0.0
        return r

    if vwap <= 0:
        r["vwap_dev"] = 0.0
        return r

    r["vwap_dev"] = (price - vwap) / vwap
    return r


def compute_elasticity(r: Dict) -> float:
    vwap_dev = abs(safe_float(r.get("vwap_dev"), 0.0))
    momentum = abs(safe_float(r.get("momentum"), 0.0))
    return min(vwap_dev / max(momentum, 0.001), 50.0)


def trade_score(r: Dict) -> float:
    score = safe_float(r.get("score"), 0.0)
    vwap_dev = abs(safe_float(r.get("vwap_dev"), 0.0))
    elasticity = safe_float(r.get("elasticity_score"), 0.0)
    return score * 0.5 + min(vwap_dev * 1500.0, 2.0) * 0.3 + min(elasticity / 8.0, 1.0) * 0.2


def allocate_capital(candidates: List[Dict]) -> Dict[str, float]:
    allocations: Dict[str, float] = {}
    grouped: Dict[str, List[Dict]] = {}

    for r in candidates:
        grouped.setdefault(r["asset_class"], []).append(r)

    for cls, rows in grouped.items():
        class_cap = TOTAL_CAPITAL * CLASS_WEIGHTS.get(cls, 0.0)
        total_score = sum(max(safe_float(r.get("trade_score"), 0.0), 0.0001) for r in rows)

        for r in rows:
            weight = safe_float(r.get("trade_score"), 0.0) / total_score if total_score else 0.0
            allocations[r["symbol"]] = max(class_cap * weight, 50.0)

    return allocations


# ================= DATA LOADERS =================
def load_crypto(symbols: List[str]) -> List[Dict]:
    results: List[Dict] = []
    headers = {"User-Agent": "Mozilla/5.0"}

    for s in symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=5d&interval=15m"
            data = requests.get(url, headers=headers, timeout=6).json()

            chart = data.get("chart", {}).get("result", [])
            if not chart:
                print(f"[CRYPTO MISS] {s}")
                continue

            quote = chart[0].get("indicators", {}).get("quote", [{}])[0]
            closes = quote.get("close", [])
            closes = [c for c in closes if c is not None]

            if len(closes) < 10:
                print(f"[CRYPTO MISS] {s}")
                continue

            price = safe_float(closes[-1], 0.0)
            if price <= 0:
                print(f"[CRYPTO MISS] {s}")
                continue

            vwap = sum(closes[-20:]) / min(len(closes), 20)
            base_5 = safe_float(closes[-5], 0.0)
            momentum = ((price - base_5) / base_5) if base_5 > 0 else 0.0

            results.append(
                {
                    "symbol": s,
                    "price": price,
                    "closes": closes[-5:],
                    "vwap": vwap,
                    "momentum": momentum,
                    "spread_bps": DEFAULT_SPREAD_BPS["crypto"],
                }
            )

            print(f"[CRYPTO OK] {s} | p={price:.2f}")

        except Exception:
            print(f"[CRYPTO MISS] {s}")
            continue

    return results


# ================= PRICE MODEL =================
def micro_price(row: Dict, pos: Dict) -> float:
    closes = row.get("closes")

    if not closes or len(closes) < 3:
        return safe_float(row.get("price"), pos["entry"])

    c1 = safe_float(closes[-1], 0.0)
    c2 = safe_float(closes[-2], 0.0)
    c3 = safe_float(closes[-3], 0.0)

    if c1 <= 0 or c2 <= 0 or c3 <= 0:
        return safe_float(row.get("price"), pos["entry"])

    delta1 = c1 - c2
    delta2 = c2 - c3
    slope = (delta1 + delta2) / 2.0

    base = c1
    pct_move = slope / base
    decay = max(0.2, 1.0 - safe_float(pos.get("cycles"), 0) * 0.15)

    return base * (1.0 + pct_move * decay)


# ================= COST / EDGE =================
def dynamic_cost_bps(r: Dict) -> float:
    cls = r["asset_class"]
    spread = safe_float(r.get("spread_bps"), DEFAULT_SPREAD_BPS.get(cls, 5.0))
    slippage = abs(safe_float(r.get("vwap_dev"), 0.0)) * 10000.0 * 0.25
    fee = BASE_FEE_BPS.get(cls, 8.0)
    return spread + slippage + fee


def expected_move_bps(r: Dict) -> float:
    vwap_component = abs(safe_float(r.get("vwap_dev"), 0.0)) * 10000.0 * 0.6
    momentum_component = abs(safe_float(r.get("momentum"), 0.0)) * 10000.0 * 0.25
    elasticity_component = min(safe_float(r.get("elasticity_score"), 0.0), 10.0) * 1.5
    return vwap_component + momentum_component + elasticity_component


def passes_profitability_gate(r: Dict) -> bool:
    expected = expected_move_bps(r)
    cost = dynamic_cost_bps(r) + SAFETY_MARGIN_BPS

    if expected <= cost * 1.25:
        print(f"[FILTERED] {r['symbol']} -> EDGE {expected:.1f}bps < COST {(cost * 1.25):.1f}bps")
        return False
    return True


# ================= ENGINE =================
def run() -> None:
    global equity, cycle_count

    print("\n=== CSS WITH PERFORMANCE DASHBOARD (PROFITABILITY FIX) ===\n")
    scorer = AIOpportunityScorer()

    while True:
        try:
            cycle_count += 1
            print(f"\n--- NEW CYCLE #{cycle_count} ---")

            rows = load_runtime_universe(PRODUCTS_NO_CRYPTO, days=3)
            rows.extend(load_crypto(PRODUCTS_BY_CLASS["crypto"]))

            clean_rows: List[Dict] = []
            for r in rows:
                symbol = r.get("symbol")
                if not symbol:
                    continue

                price = safe_float(r.get("price"), 0.0)
                if price <= 0:
                    continue

                r["asset_class"] = symbol_asset_class(symbol)
                r = ensure_vwap_dev(r)
                r["elasticity_score"] = compute_elasticity(r)
                r["score"] = safe_float(scorer.score(r), 0.0)
                r["trade_score"] = trade_score(r)
                clean_rows.append(r)

            row_map = {r["symbol"]: r for r in clean_rows}

            candidates: List[Dict] = []

            for r in clean_rows:
                print(f"[SCAN] {r['symbol']} | {r['asset_class']} | tscore={r['trade_score']:.4f}")

                strong = False

                if r["asset_class"] == "futures":
                    strong = r["trade_score"] >= 0.65 and abs(r["vwap_dev"]) >= 0.0015
                elif r["asset_class"] == "crypto":
                    strong = r["trade_score"] >= 0.42 and abs(r["vwap_dev"]) >= 0.0020
                else:
                    strong = False

                if not strong:
                    print(f"[REJECTED] {r['symbol']} -> weak structure")
                    continue

                if passes_profitability_gate(r):
                    candidates.append(r)

            allocations = allocate_capital(candidates)
            class_open = count_open_positions_by_class()

            # ===== ENTRIES =====
            for r in sorted(candidates, key=lambda x: x["trade_score"], reverse=True):
                sym = r["symbol"]
                cls = r["asset_class"]

                if sym in open_positions:
                    continue

                if len(open_positions) >= MAX_OPEN_POSITIONS:
                    break

                if class_open.get(cls, 0) >= CLASS_LIMITS.get(cls, 0):
                    continue

                price = safe_float(r.get("price"), 0.0)
                if price <= 0:
                    continue

                capital = allocations.get(sym, 50.0)

                if cls == "crypto":
                    tp = 0.0180
                    sl = -0.0070
                else:
                    tp = 0.0140
                    sl = -0.0060

                open_positions[sym] = {
                    "entry": price,
                    "capital": capital,
                    "tp": tp,
                    "sl": sl,
                    "cycles": 0,
                }

                last_prices[sym] = price
                class_open[cls] = class_open.get(cls, 0) + 1

                print(f"[ENTRY] {sym} @ {price:.2f} | {cls} | capital={capital:.2f}")

                log_trade(
                    {
                        "type": "ENTRY",
                        "symbol": sym,
                        "asset_class": cls,
                        "price": price,
                        "capital": capital,
                        "cycle": cycle_count,
                        "timestamp": time.time(),
                    }
                )

            # ===== POSITION MANAGEMENT =====
            for sym, pos in list(open_positions.items()):
                row = row_map.get(sym)
                if not row:
                    print(f"[SKIP] {sym} -> no fresh row")
                    continue

                price = micro_price(row, pos)
                if price <= 0:
                    continue

                last_prices[sym] = price
                entry = safe_float(pos.get("entry"), 0.0)
                capital = safe_float(pos.get("capital"), 0.0)

                if entry <= 0:
                    continue

                pnl_pct = (price - entry) / entry
                pnl_value = pnl_pct * capital

                pos["cycles"] += 1

                should_exit = (
                    pnl_pct >= safe_float(pos.get("tp"), 0.0)
                    or pnl_pct <= safe_float(pos.get("sl"), 0.0)
                    or safe_float(pos.get("cycles"), 0) >= MAX_CYCLES
                )

                if should_exit:
                    equity += pnl_value
                    stats["pnl"] += pnl_value
                    stats["trades"] += 1

                    if pnl_value > 0:
                        stats["wins"] += 1
                    else:
                        stats["losses"] += 1

                    print(f"[EXIT] {sym} PnL: {pnl_value:+.2f}")

                    log_trade(
                        {
                            "type": "EXIT",
                            "symbol": sym,
                            "entry": entry,
                            "exit": price,
                            "pnl": pnl_value,
                            "pnl_pct": pnl_pct,
                            "cycles": pos["cycles"],
                            "cycle": cycle_count,
                            "timestamp": time.time(),
                        }
                    )

                    del open_positions[sym]

            print(f"Open Positions: {len(open_positions)}")
            print_performance()

            time.sleep(5)

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print("ERROR:", e)
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    run()